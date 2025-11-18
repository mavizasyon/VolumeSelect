# Volume Select - Blender Addon

**Volume Select** is a Blender 4.x addon to select loose mesh components (vertices, edges, faces) based on **bounding-box volumes**. You can define multiple threshold ranges and select all components that fit in any range.

## Features

- Select by bounding-box volume (world-space).
- Multiple draggable threshold ranges.
- Min/Max toggles for each range.
- Works in Edit Mode for vertices, edges, or faces.
- Tutorial included inside Blender.

## Installation

1. Download the repository as ZIP or clone it.
2. Open Blender > Edit > Preferences > Add-ons > Install.
3. Select the folder containing `__init__.py`.
4. Enable the addon.

## Usage

1. Select a mesh object and enter Edit Mode.
2. Open the **Volume Select** panel in the sidebar.
3. Add threshold ranges and enable Min/Max as needed.
4. Click **Select by Threshold Ranges** to select components.
