# Surface Projection Architecture

## Overview

The surface projection system is designed to correct 3D vehicle detection positions by projecting them onto appropriate surfaces. The architecture supports multiple projection methods through a unified configuration interface.

## Current Implementation: Ground Plane Projection

### What It Does
- Projects 3D detection centers to a flat horizontal plane (typically z=0)
- Corrects monocular depth estimation errors using accurate camera calibration
- Scales bounding boxes based on perspective changes due to depth correction

### How It Works
1. **Ray Casting**: Creates a ray from camera center through detection center
2. **Plane Intersection**: Finds where the ray intersects the ground plane (z=ground_plane_z)
3. **Position Correction**: Updates detection translation to intersection point
4. **Scale Correction**: Adjusts bounding box size based on depth change ratio

### Configuration
```json
{
  "project_3d_detections_to_surface": {
    "enabled": true,
    "scale_bbox_with_perspective": true,
    "apply_to_categories": ["car", "truck", "bus", "motorcycle", "trailer", "van"],
    "surface_type": "ground_plane",
    "ground_plane_z": 0.0
  }
}
```

## Future Enhancement: Terrain Projection

### Design Intent
- Projects detections to actual terrain surface using elevation maps
- Handles sloped terrain, hills, and complex ground geometry
- Maintains the same interface but uses different projection algorithm

### Configuration (Future)
```json
{
  "project_3d_detections_to_surface": {
    "enabled": true,
    "scale_bbox_with_perspective": true, 
    "apply_to_categories": ["car", "truck", "bus", "motorcycle", "trailer", "van"],
    "surface_type": "terrain",
    "terrain_data": {
      "elevation_map": "/path/to/elevation.tif",
      "resolution": 1.0,
      "fallback_to_ground_plane": true
    }
  }
}
```

## Code Architecture

### Function Hierarchy
```
_apply_surface_projection()           # Main dispatch function
├── _should_apply_surface_projection() # Category and config checking
├── _calculate_min_distance_threshold() # Safety distance calculation
├── _project_to_ground_plane()         # Current implementation
└── _project_to_terrain()              # Future implementation (placeholder)
```

### Integration Point
- **Location**: `MovingObject.mapObjectDetectionToWorld()` method
- **Trigger**: Category matches configured list AND projection enabled
- **Effect**: Modifies detection `translation` and optionally `size` before world transformation

## Benefits of This Approach

### Extensibility
- Easy to add new surface types (water level, building floors, etc.)
- Configuration-driven category selection
- Unified interface for all projection methods

### Flexibility
- Per-category configuration possible
- Easy to enable/disable without code changes
- Support for different surface parameters

### Maintainability
- Clear separation between projection algorithms
- Consistent error handling and logging
- Configuration validation in one place

## Implementation Status

### ✅ Completed
- Ground plane projection algorithm
- Configuration-driven category selection  
- Integration into detection pipeline
- Perspective-based bounding box scaling
- Debug logging and error handling

### 🚧 Future Work
- Terrain elevation map support
- Performance optimization for large scenes
- Advanced projection methods (curved surfaces, etc.)
- Configuration validation and error reporting

## Usage

The system automatically applies surface projection to configured vehicle categories during the detection-to-world transformation process. No manual intervention required - everything is controlled through the tracker configuration file.

### Debugging
Enable debug logging to see projection decisions:
```
log.debug("Surface projection: Processing {category} detection")
log.debug("Surface projection: {original} -> {projected} ({reason})")
```

### Configuration Changes
Modify `tracker-config.json` to:
- Enable/disable projection: `"enabled": true/false`
- Add/remove categories: `"apply_to_categories": [...]`
- Change surface type: `"surface_type": "ground_plane"` or `"terrain"`
- Adjust ground level: `"ground_plane_z": 0.0`
