import QtQuick

Image {
  id: root
  property color color: "#ffffff"
  source: Qt.resolvedUrl("assets/skillsync.svg")
  fillMode: Image.PreserveAspectFit
  sourceSize.width: Math.max(64, Math.round(width * 3))
  sourceSize.height: Math.max(64, Math.round(height * 3))
  smooth: true
  asynchronous: false
}
