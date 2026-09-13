pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "Model.js" as Model

Item {
  id: row

  required property var modelData
  property string mode: "library"
  property bool busy: false
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  readonly property color dim: Qt.darker(foreground, 1.45)
  readonly property bool discover: mode === "discover"

  signal openRequested(string path)
  signal removeRequested(string folder)
  signal installRequested(string spec, string name)
  signal pageRequested(string url)

  width: parent ? parent.width : implicitWidth
  implicitHeight: card.implicitHeight + Style.space(6)

  Rectangle {
    id: card
    width: parent.width
    implicitHeight: content.implicitHeight + Style.space(18)
    radius: Style.cornerRadius > 0 ? Style.cornerRadius : 4
    color: hover.hovered ? Style.hoverFillFor(row.foreground, Color.accent) : "transparent"

    HoverHandler { id: hover }

    ColumnLayout {
      id: content
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.leftMargin: Style.space(10)
      anchors.rightMargin: Style.space(10)
      anchors.topMargin: Style.space(9)
      spacing: Style.space(6)

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(10)

        Rectangle {
          Layout.preferredWidth: Style.space(28)
          Layout.preferredHeight: Style.space(28)
          radius: 6
          color: Style.selectedFillFor(row.foreground, Color.accent)

          Text {
            anchors.centerIn: parent
            text: row.discover && Number(row.modelData.rank || 0) > 0
              ? String(row.modelData.rank)
              : Model.initialFor(row.modelData.name || row.modelData.folder)
            textFormat: Text.PlainText
            color: row.foreground
            font.family: row.fontFamily
            font.pixelSize: Number(row.modelData.rank || 0) >= 100 ? Style.font.caption : Style.font.bodySmall
            font.bold: true
          }
        }

        ColumnLayout {
          Layout.fillWidth: true
          spacing: Style.space(2)

          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)

            Text {
              Layout.fillWidth: true
              text: row.modelData.name || row.modelData.folder || ""
              textFormat: Text.PlainText
              elide: Text.ElideRight
              color: row.foreground
              font.family: row.fontFamily
              font.pixelSize: Style.font.body
              font.bold: true
            }

            Text {
              visible: row.discover && Number(row.modelData.installs || 0) > 0
              text: row.modelData.installsLabel || Model.formatInstalls(row.modelData.installs)
              textFormat: Text.PlainText
              color: row.dim
              font.family: row.fontFamily
              font.pixelSize: Style.font.caption
            }

            Text {
              visible: row.discover && row.modelData.verified === true
              text: "VERIFIED"
              textFormat: Text.PlainText
              color: Color.accent
              font.family: row.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }

            Text {
              visible: !row.discover
              text: Model.originLabel(row.modelData)
              textFormat: Text.PlainText
              color: row.modelData.canonical === true ? row.dim : Color.accent
              font.family: row.fontFamily
              font.pixelSize: Style.font.caption
            }
          }

          Text {
            Layout.fillWidth: true
            visible: String(row.discover ? (row.modelData.source || "") : (row.modelData.description || "")) !== ""
            text: row.discover
              ? String(row.modelData.source || "")
              : String(row.modelData.description || "")
            textFormat: Text.PlainText
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.WordWrap
            color: row.dim
            font.family: row.fontFamily
            font.pixelSize: Style.font.caption
          }

          Text {
            Layout.fillWidth: true
            visible: row.discover
              && String(row.modelData.skillId || "") !== ""
              && String(row.modelData.skillId) !== String(row.modelData.name || "")
            text: String(row.modelData.skillId || "")
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: row.dim
            font.family: row.fontFamily
            font.pixelSize: Style.font.caption
            opacity: 0.85
          }
        }

        RowLayout {
          spacing: Style.space(4)
          Layout.alignment: Qt.AlignTop

          Button {
            visible: !row.discover
            iconText: "\uf07c"
            tooltipText: "Open SKILL.md"
            enabled: !row.busy
            foreground: row.foreground
            accent: Color.accent
            fontFamily: row.fontFamily
            fontSize: Style.font.caption
            horizontalPadding: Style.space(8)
            verticalPadding: Style.space(3)
            onClicked: row.openRequested(row.modelData.path)
          }

          Button {
            visible: !row.discover && row.modelData.canonical === true
            iconText: "\uf1f8"
            tooltipText: "Remove from this machine"
            enabled: !row.busy
            foreground: row.foreground
            accent: Color.urgent
            fontFamily: row.fontFamily
            fontSize: Style.font.caption
            horizontalPadding: Style.space(8)
            verticalPadding: Style.space(3)
            onClicked: row.removeRequested(row.modelData.folder)
          }

          Button {
            visible: row.discover && row.modelData.installed === true
            text: "Installed"
            enabled: false
            bordered: true
            foreground: row.dim
            accent: Color.accent
            fontFamily: row.fontFamily
            fontSize: Style.font.caption
            horizontalPadding: Style.space(8)
            verticalPadding: Style.space(3)
          }

          Button {
            visible: row.discover && row.modelData.installed !== true
            text: "Install"
            tooltipText: "Install globally with the skills CLI"
            enabled: !row.busy && String(row.modelData.installSpec || "") !== ""
            bordered: true
            foreground: row.foreground
            accent: Color.accent
            fontFamily: row.fontFamily
            fontSize: Style.font.caption
            horizontalPadding: Style.space(8)
            verticalPadding: Style.space(3)
            onClicked: row.installRequested(row.modelData.installSpec, row.modelData.name)
          }

          Button {
            visible: row.discover && String(row.modelData.url || "") !== ""
            iconText: "\uf08e"
            tooltipText: "Open on skills.sh"
            foreground: row.foreground
            accent: Color.accent
            fontFamily: row.fontFamily
            fontSize: Style.font.caption
            horizontalPadding: Style.space(8)
            verticalPadding: Style.space(3)
            onClicked: row.pageRequested(row.modelData.url)
          }
        }
      }

    }
  }
}
