pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Item {
  id: row

  required property var modelData
  property bool busy: false
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  readonly property color dim: Qt.darker(foreground, 1.45)
  readonly property bool wired: modelData.wired === true
  readonly property bool nativeShared: modelData.sharedCanonical === true

  signal wireRequested(string agentId, string name, int uniqueCount)
  signal openRequested(string path)

  width: parent ? parent.width : implicitWidth
  implicitHeight: card.implicitHeight + Style.space(6)

  Rectangle {
    id: card
    width: parent.width
    implicitHeight: content.implicitHeight + Style.space(16)
    radius: Style.cornerRadius > 0 ? Style.cornerRadius : 4
    color: hover.hovered ? Style.hoverFillFor(row.foreground, Color.accent) : "transparent"

    HoverHandler { id: hover }

    RowLayout {
      id: content
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.leftMargin: Style.space(10)
      anchors.rightMargin: Style.space(10)
      anchors.topMargin: Style.space(8)
      spacing: Style.space(10)

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(2)

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.space(8)

          Text {
            text: row.modelData.name || row.modelData.id || ""
            textFormat: Text.PlainText
            color: row.foreground
            font.family: row.fontFamily
            font.pixelSize: Style.font.body
            font.bold: true
          }

          Text {
            visible: row.nativeShared
            text: "NATIVE"
            textFormat: Text.PlainText
            color: Color.accent
            font.family: row.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }

          Text {
            visible: !row.nativeShared && row.wired
            text: "WIRED"
            textFormat: Text.PlainText
            color: Color.accent
            font.family: row.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }

          Item { Layout.fillWidth: true }

          Text {
            text: row.wired
              ? Number(row.modelData.skillCount || 0) + " skills"
              : (Number(row.modelData.uniqueCount || 0) + " unique")
            textFormat: Text.PlainText
            color: row.dim
            font.family: row.fontFamily
            font.pixelSize: Style.font.caption
          }
        }

        Text {
          Layout.fillWidth: true
          text: row.nativeShared
            ? "Reads the shared library directly"
            : row.wired
              ? "Points at the shared library"
              : (row.modelData.dir || "")
          textFormat: Text.PlainText
          elide: Text.ElideMiddle
          color: row.dim
          font.family: row.fontFamily
          font.pixelSize: Style.font.caption
        }
      }

      Button {
        iconText: "\uf07c"
        tooltipText: "Open skills directory"
        foreground: row.foreground
        accent: Color.accent
        fontFamily: row.fontFamily
        fontSize: Style.font.caption
        horizontalPadding: Style.space(8)
        verticalPadding: Style.space(3)
        onClicked: row.openRequested(row.modelData.dir)
      }

      Button {
        visible: row.modelData.wireable === true && !row.wired
        text: "Use shared library"
        tooltipText: "Move unique skills into ~/.agents/skills and point this harness at that folder"
        enabled: !row.busy
        bordered: true
        foreground: row.foreground
        accent: Color.accent
        fontFamily: row.fontFamily
        fontSize: Style.font.caption
        horizontalPadding: Style.space(8)
        verticalPadding: Style.space(3)
        onClicked: row.wireRequested(row.modelData.id, row.modelData.name, Number(row.modelData.uniqueCount || 0))
      }
    }
  }
}
