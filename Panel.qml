pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "jbicks.skills"
  ipcTarget: "jbicks.skills"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color dim: Qt.darker(contentForeground, 1.5)
  readonly property color panelBackground: Color.popups.background

  property string tab: "library"
  property string searchText: ""
  property string originFilter: "local"
  property var scanData: ({ skills: [], harnesses: [], skillCount: 0, harnessCount: 0, unwiredCount: 0, wiredCount: 0 })
  property var remoteSkills: []
  property string remoteQuery: ""
  property bool scanning: false
  property bool searching: false
  property bool acting: false
  property string statusText: ""
  property string statusKind: ""
  property double lastScanMs: 0
  property bool confirmOpen: false
  property string confirmKind: ""
  property string confirmMessage: ""
  property string confirmAction: ""
  property var confirmArgs: []

  readonly property string helper: {
    var url = String(Qt.resolvedUrl("scripts/skillkit.py"))
    return url.replace(/^file:\/\/localhost/, "").replace(/^file:\/\//, "")
  }
  readonly property bool showBundled: root.setting("showBundled", false) === true || root.originFilter === "bundled"
  readonly property var visibleSkills: Model.filterSkills(root.scanData.skills, root.searchText, root.originFilter)
  readonly property var visibleRemote: Model.filterRemote(root.remoteSkills, "", false)
  readonly property var visibleHarnesses: root.scanData.harnesses || []
  readonly property int unwiredCount: Number(root.scanData.unwiredCount || 0)
  readonly property bool busy: root.scanning || root.searching || root.acting
  readonly property string headerSummary: {
    if (root.statusText !== "" && root.statusKind !== "error") return root.statusText
    if (root.tab === "discover") {
      if (root.searching) return "Searching skills.sh…"
      if (root.remoteQuery !== "") return root.visibleRemote.length + " matches on skills.sh"
      return "Top " + root.visibleRemote.length + " on skills.sh"
    }
    if (root.tab === "harnesses") {
      var n = visibleHarnesses.length
      var extra = root.unwiredCount > 0 ? " · " + root.unwiredCount + " not on the shared folder" : " · all on the shared folder"
      return n + " harness" + (n === 1 ? "" : "es") + extra
    }
    return Model.summaryLine(root.scanData)
  }

  function open() {
    root.controller.show()
    root.primeFocus()
    if (Date.now() - root.lastScanMs > 15000) root.refresh()
  }
  function openDiscover() {
    root.open()
    root.changeTab("discover")
  }
  function close() {
    root.confirmOpen = false
    root.controller.hide()
  }
  function toggle() { root.opened ? root.close() : root.open() }
  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }
  function primeFocus() {
    if (searchField) searchField.forceActiveFocus()
    focusRetry.restart()
  }

  function runHelper(process, args) {
    var cmd = ["python3", root.helper]
    for (var i = 0; i < args.length; i++) cmd.push(args[i])
    process.command = cmd
    process.running = true
  }

  function refresh() {
    if (root.scanning) return
    root.scanning = true
    root.statusText = "Scanning installed skills…"
    root.statusKind = ""
    var args = ["scan"]
    if (root.showBundled) args.push("--bundled")
    root.runHelper(scanProcess, args)
  }

  function applyScan(text) {
    root.scanning = false
    var payload = Model.parsePayload(text)
    if (!payload.ok) {
      root.statusText = payload.error || "Scan failed"
      root.statusKind = "error"
      return
    }
    root.scanData = payload
    root.lastScanMs = Date.now()
    root.statusText = ""
    root.statusKind = ""
  }

  function requestDiscover() {
    if (root.searching) return
    root.searching = true
    root.statusText = "Loading skills.sh leaderboard…"
    root.statusKind = ""
    root.remoteQuery = ""
    root.runHelper(searchProcess, ["discover"])
  }

  function requestSearch(query) {
    var q = String(query || "").trim()
    if (q.length < 2) {
      root.requestDiscover()
      return
    }
    root.searching = true
    root.statusText = "Searching skills.sh…"
    root.statusKind = ""
    root.remoteQuery = q
    root.runHelper(searchProcess, ["search", q, "--limit", "40"])
  }

  function applySearch(text) {
    root.searching = false
    var payload = Model.parsePayload(text)
    if (!payload.ok) {
      root.statusText = payload.error || "Search failed"
      root.statusKind = "error"
      return
    }
    root.remoteSkills = payload.skills || []
    root.remoteQuery = payload.query || root.remoteQuery
    root.statusText = ""
    root.statusKind = ""
  }

  function runAction(args, pendingText) {
    if (root.acting) return
    root.acting = true
    root.statusText = pendingText || "Working…"
    root.statusKind = ""
    root.runHelper(actionProcess, args)
  }

  function applyAction(text) {
    root.acting = false
    var payload = Model.parsePayload(text)
    if (!payload.ok) {
      root.statusText = payload.error || "Action failed"
      root.statusKind = "error"
      return
    }
    if (payload.errors && payload.errors.length > 0)
      root.statusText = payload.errors.join("; ")
    else if (payload.adopted)
      root.statusText = payload.already
        ? (payload.name || "Harness") + " already uses the shared library"
        : "Pointed " + (payload.name || "harness") + " at the shared library"
    else if (payload.wired && payload.count !== undefined)
      root.statusText = payload.count === 0 ? "Every harness already uses the shared library" : "Wired " + payload.count + " harness" + (payload.count === 1 ? "" : "es")
    else if (payload.canonicalRemoved)
      root.statusText = "Removed " + (payload.name || "skill")
    else if (payload.source)
      root.statusText = "Installed " + (payload.skill || payload.source)
    else
      root.statusText = "Done"
    root.statusKind = ""
    root.refresh()
    if (root.tab === "discover") {
      if (root.remoteQuery) root.requestSearch(root.remoteQuery)
      else root.requestDiscover()
    }
  }

  function askConfirm(kind, message, action, args) {
    root.confirmKind = kind
    root.confirmMessage = message
    root.confirmAction = action
    root.confirmArgs = args
    root.confirmOpen = true
  }

  function performConfirm() {
    var action = root.confirmAction
    var args = root.confirmArgs
    root.confirmOpen = false
    if (action === "install")
      root.runAction(["install", args[0]], "Installing " + args[1] + "…")
    else if (action === "remove")
      root.runAction(["remove", args[0]], "Removing " + args[0] + "…")
    else if (action === "wire")
      root.runAction(["wire", args[0]], "Pointing " + args[1] + " at the shared library…")
    else if (action === "wire-all")
      root.runAction(["wire-all"], "Pointing every harness at the shared library…")
  }

  function openPath(path) {
    if (!path) return
    Qt.openUrlExternally("file://" + path)
  }

  function changeTab(value) {
    root.tab = value
    if (value === "discover" && root.remoteSkills.length === 0 && !root.searching)
      root.requestDiscover()
    root.primeFocus()
  }

  Timer {
    id: focusRetry
    interval: 120
    repeat: false
    onTriggered: if (root.opened && searchField) searchField.forceActiveFocus()
  }

  Timer {
    id: searchDebounce
    interval: 380
    repeat: false
    onTriggered: {
      if (root.tab !== "discover") return
      root.requestSearch(root.searchText)
    }
  }

  function processText(stdout, stderr) {
    var out = String(stdout || "").trim()
    if (out) return out
    return String(stderr || "").trim()
  }

  Process {
    id: scanProcess
    onExited: root.applyScan(root.processText(scanStdout.text, scanStderr.text))
    stdout: StdioCollector { id: scanStdout; waitForEnd: true }
    stderr: StdioCollector { id: scanStderr; waitForEnd: true }
  }

  Process {
    id: searchProcess
    onExited: root.applySearch(root.processText(searchStdout.text, searchStderr.text))
    stdout: StdioCollector { id: searchStdout; waitForEnd: true }
    stderr: StdioCollector { id: searchStderr; waitForEnd: true }
  }

  Process {
    id: actionProcess
    onExited: root.applyAction(root.processText(actionStdout.text, actionStderr.text))
    stdout: StdioCollector { id: actionStdout; waitForEnd: true }
    stderr: StdioCollector { id: actionStderr; waitForEnd: true }
  }

  Component.onCompleted: root.refresh()

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(560))
    contentHeight: panel.fittedContentHeight(Math.round(Style.space(560)))

    Rectangle {
      id: appHeader
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: parent.right
      height: headerColumn.implicitHeight + Style.space(16)
      z: 20
      color: root.panelBackground

      ColumnLayout {
        id: headerColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: Style.space(16)
        anchors.rightMargin: Style.space(16)
        anchors.topMargin: Style.space(8)
        spacing: Style.space(8)

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.space(14)

          Logo {
            Layout.preferredWidth: Style.space(36)
            Layout.preferredHeight: Style.space(36)
            Layout.alignment: Qt.AlignVCenter
            color: Style.selectedStateColor(root.contentForeground, Color.accent)
          }

          ColumnLayout {
            Layout.fillWidth: true
            spacing: Style.space(2)

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.space(8)

              Text {
                text: "SKILLSYNC"
                color: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.title * 1.5
                font.bold: true
                Layout.fillWidth: true
              }

              Button {
                text: "skills.sh"
                tooltipText: "Open the public skills directory"
                bordered: true
                foreground: root.contentForeground
                accent: Color.accent
                fontFamily: root.contentFontFamily
                fontSize: Style.font.caption
                horizontalPadding: Style.space(8)
                verticalPadding: Style.space(3)
                onClicked: Qt.openUrlExternally("https://skills.sh")
              }

              Button {
                visible: root.unwiredCount > 0
                text: "Wire all"
                tooltipText: "Point every installed harness at ~/.agents/skills"
                enabled: !root.busy
                bordered: true
                foreground: root.contentForeground
                accent: Color.accent
                fontFamily: root.contentFontFamily
                fontSize: Style.font.caption
                horizontalPadding: Style.space(8)
                verticalPadding: Style.space(3)
                onClicked: root.askConfirm(
                  "wire-all",
                  "Move unique skills into ~/.agents/skills and point every installed harness at that folder?",
                  "wire-all",
                  []
                )
              }
            }

            Text {
              text: root.headerSummary
              textFormat: Text.PlainText
              color: root.statusKind === "error" ? Color.urgent : root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              Layout.fillWidth: true
              elide: Text.ElideRight
            }
          }
        }

        ButtonGroup {
          Layout.fillWidth: true
          foreground: root.contentForeground
          accent: Color.accent
          fontFamily: root.contentFontFamily
          fontSize: Style.font.caption
          value: root.tab
          options: [
            { value: "library", label: "Library" },
            { value: "discover", label: "Discover" },
            { value: "harnesses", label: "Harnesses" }
          ]
          onChanged: root.changeTab(value)
        }

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.space(8)
          visible: root.tab !== "harnesses"

          TextField {
            id: searchField
            Layout.fillWidth: true
            foreground: root.contentForeground
            placeholderText: root.tab === "discover" ? "Search skills.sh" : "Filter installed skills"
            text: root.searchText
            onTextChanged: {
              root.searchText = text
              if (root.tab === "discover") searchDebounce.restart()
            }
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                if (root.searchText !== "") {
                  root.searchText = ""
                  searchField.text = ""
                  event.accepted = true
                } else {
                  root.close()
                  event.accepted = true
                }
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (root.tab === "discover") {
                  searchDebounce.stop()
                  root.requestSearch(root.searchText)
                }
                event.accepted = true
              }
            }
          }

          Dropdown {
            id: filterDropdown
            visible: root.tab === "library"
            width: Style.space(140)
            foreground: root.contentForeground
            accent: Color.accent
            fontFamily: root.contentFontFamily
            showLabel: false
            value: root.originFilter
            options: [
              { value: "local", label: "Library" },
              { value: "orphans", label: "Not shared" },
              { value: "bundled", label: "Bundled" }
            ]
            onChanged: {
              root.originFilter = value
              if (value === "bundled") root.refresh()
            }
          }

          Button {
            iconText: "\uf021"
            tooltipText: "Refresh"
            enabled: !root.busy
            foreground: root.contentForeground
            accent: Color.accent
            fontFamily: root.contentFontFamily
            fontSize: Style.font.bodySmall
            horizontalPadding: Style.space(10)
            verticalPadding: Style.space(5)
            onClicked: {
              if (root.tab === "discover") {
                if (root.searchText.trim().length >= 2) root.requestSearch(root.searchText)
                else root.requestDiscover()
              } else {
                root.refresh()
              }
            }
          }
        }

      }
    }

    Item {
      id: panelContent
      anchors.fill: parent
      anchors.topMargin: appHeader.height
      clip: true

      PanelKeyCatcher {
        id: keyCatcher
        anchors.fill: parent
        blocked: searchField.activeFocus || filterDropdown.popupOpen
        onCloseRequested: {
          if (root.confirmOpen) root.confirmOpen = false
          else root.close()
        }
        onActivateRequested: if (root.confirmOpen) root.performConfirm()
        onReturnRequested: if (root.confirmOpen) root.performConfirm()
        onMoveRequested: function() { if (root.confirmOpen) return }
        onTabRequested: function(direction) {
          if (root.confirmOpen) return
          root.switchPanel(direction)
        }
        onTextKey: function(t) {
          if (root.confirmOpen) return
          if (t === "1") root.changeTab("library")
          else if (t === "2") root.changeTab("discover")
          else if (t === "3") root.changeTab("harnesses")
          else if (t === "/") root.primeFocus()
          else if (t === "r" || t === "R") root.refresh()
        }
      }

      Flickable {
        id: libraryList
        visible: root.tab === "library"
        anchors.fill: parent
        anchors.margins: Style.space(12)
        clip: true
        contentWidth: width
        contentHeight: libraryColumn.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: libraryColumn
          width: libraryList.width
          spacing: Style.space(2)

          Repeater {
            model: root.visibleSkills
            SkillRow {
              width: libraryColumn.width
              mode: "library"
              busy: root.busy
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              onOpenRequested: function(path) { root.openPath(path) }
              onRemoveRequested: function(folder) {
                root.askConfirm("remove", "Remove " + folder + " from the shared library?", "remove", [folder])
              }
            }
          }
        }
      }

      Flickable {
        id: discoverList
        visible: root.tab === "discover"
        anchors.fill: parent
        anchors.margins: Style.space(12)
        clip: true
        contentWidth: width
        contentHeight: discoverColumn.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: discoverColumn
          width: discoverList.width
          spacing: Style.space(2)

          Repeater {
            model: root.visibleRemote
            SkillRow {
              width: discoverColumn.width
              mode: "discover"
              busy: root.busy
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              onInstallRequested: function(spec, name) {
                root.askConfirm(
                  "install",
                  "Skills are unsandboxed instructions your agents will follow. Install " + name + " from " + spec + " into the shared library?",
                  "install",
                  [spec, name]
                )
              }
              onPageRequested: function(url) { Qt.openUrlExternally(url) }
            }
          }
        }
      }

      Flickable {
        id: harnessList
        visible: root.tab === "harnesses"
        anchors.fill: parent
        anchors.margins: Style.space(12)
        clip: true
        contentWidth: width
        contentHeight: harnessColumn.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: harnessColumn
          width: harnessList.width
          spacing: Style.space(2)

          Repeater {
            model: root.visibleHarnesses
            HarnessRow {
              width: harnessColumn.width
              busy: root.busy
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              onOpenRequested: function(path) { root.openPath(path) }
              onWireRequested: function(agentId, name, uniqueCount) {
                var extra = uniqueCount > 0
                  ? " Move " + uniqueCount + " unique skill" + (uniqueCount === 1 ? "" : "s") + " into the shared library first."
                  : ""
                root.askConfirm(
                  "wire",
                  "Point " + name + " at ~/.agents/skills?" + extra,
                  "wire",
                  [agentId, name]
                )
              }
            }
          }
        }
      }

      Text {
        anchors.centerIn: parent
        width: parent.width - Style.space(40)
        visible: !root.busy && (
          (root.tab === "library" && root.visibleSkills.length === 0) ||
          (root.tab === "discover" && root.visibleRemote.length === 0) ||
          (root.tab === "harnesses" && root.visibleHarnesses.length === 0)
        )
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        color: root.dim
        font.family: root.contentFontFamily
        font.pixelSize: Style.font.body
        text: root.tab === "discover"
          ? "Search skills.sh, or wait for the leaderboard to load."
          : root.tab === "harnesses"
            ? "No coding agents detected on this machine."
            : root.originFilter === "orphans"
              ? "Every skill is already in the shared library."
              : "No skills in the library yet. Use Discover to install some."
      }
    }

    ConfirmDialog {
      anchors.fill: parent
      opened: root.confirmOpen
      z: 30
      message: root.confirmMessage
      confirmText: root.confirmKind === "remove" ? "Remove" : (root.confirmKind === "install" ? "Install" : "Wire")
      background: root.panelBackground
      foreground: root.contentForeground
      fontFamily: root.contentFontFamily
      cornerRadius: Style.cornerRadius
      onCanceled: root.confirmOpen = false
      onConfirmed: root.performConfirm()
    }
  }

}
