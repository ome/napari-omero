import numpy as np
from omero_rois import mask_from_binary_image

from omero.gateway import ImageWrapper
from omero.rtypes import rdouble, rint, rstring
from omero.model import (
    EllipseI,
    ImageI,
    LineI,
    PointI,
    PolygonI,
    PolylineI,
    RectangleI,
    RoiI,
)


def create_roi(image: ImageWrapper, shapes: list) -> RoiI:
    updateService = image._conn.getUpdateService()
    roi = RoiI()
    # use the omero.model.ImageI that underlies the 'image' wrapper
    roi.setImage(image._obj)
    for shape in shapes:
        roi.addShape(shape)
    # Save the ROI (saves any linked shapes too)
    return updateService.saveAndReturnObject(roi, image._conn.SERVICE_OPTS)

def get_x(coordinate):
    return coordinate[-1]


def get_y(coordinate):
    return coordinate[-2]


def get_t(coordinate):
    return coordinate[0]


def get_z(coordinate):
    return coordinate[1]


def create_omero_point(data):
    point = PointI()
    point.x = rdouble(get_x(data))
    point.y = rdouble(get_y(data))
    point.theZ = rint(get_z(data))
    point.theT = rint(get_t(data))
    return point


def create_omero_shape(shape_type, data):
    # "line", "path", "polygon", "rectangle", "ellipse"
    # NB: assume all points on same plane.
    # Use first point to get Z and T index
    z_index = get_z(data[0])
    t_index = get_t(data[0])
    shape = None
    if shape_type == "line":
        shape = LineI()
        shape.x1 = rdouble(get_x(data[0]))
        shape.y1 = rdouble(get_y(data[0]))
        shape.x2 = rdouble(get_x(data[1]))
        shape.y2 = rdouble(get_y(data[1]))
    elif shape_type in ["path", "polygon"]:
        shape = PolylineI() if shape_type == "path" else PolygonI()
        # points = "10,20, 50,150, 200,200, 250,75"
        points = [f"{get_x(d)},{get_y(d)}" for d in data]
        shape.points = rstring(", ".join(points))
    elif shape_type in ["rectangle", "ellipse"]:
        # corners go anti-clockwise starting top-left
        x1 = get_x(data[0])
        x2 = get_x(data[1])
        x3 = get_x(data[2])
        x4 = get_x(data[3])
        y1 = get_y(data[0])
        y2 = get_y(data[1])
        y3 = get_y(data[2])
        y4 = get_y(data[3])
        if shape_type == "rectangle":
            # Rectangle not rotated
            if x1 == x2:
                shape = RectangleI()
                # TODO: handle 'updside down' rectangle x3 < x1
                shape.x = rdouble(x1)
                shape.y = rdouble(y1)
                shape.width = rdouble(x3 - x1)
                shape.height = rdouble(y2 - y1)
            else:
                # Rotated Rectangle - save as Polygon
                shape = PolygonI()
                points_str = f"{x1},{y1}, {x2},{y2}, {x3},{y3}, {x4},{y4}"
                shape.points = rstring(points_str)
        elif shape_type == "ellipse":
            # Ellipse not rotated (ignore floating point rouding)
            if int(x1) == int(x2):
                shape = EllipseI()
                shape.x = rdouble((x1 + x3) / 2)
                shape.y = rdouble((y1 + y2) / 2)
                shape.radiusX = rdouble(abs(x3 - x1) / 2)
                shape.radiusY = rdouble(abs(y2 - y1) / 2)
            else:
                # TODO: Need to calculate transformation matrix
                print("Rotated Ellipse not yet supported!")

    if shape is not None:
        shape.theZ = rint(z_index)
        shape.theT = rint(t_index)
    return shape


def save_labels(layer, image: ImageWrapper) -> list[RoiI]:
    """
    Saves masks from a 5D image (no C dimension).

    Each non-zero value in the labels data
    is used to create an ROI in OMERO with a
    Shape Mask created for each Z/T plane of
    the mask.
    """
    import pandas as pd
    # for each label value, check if we have any masks
    masks_4d = np.asarray(layer.data)
    rois = []
    for v in range(1, masks_4d.max() + 1):
        # Check if ROI already has an OMERO id
        # If it has one, it already exists on the remote
        roi_id_local = layer.features.iloc[v]["roi_id"]
        shape_id_local = layer.features.iloc[v]["shape_id"]

        if pd.isna(shape_id_local) and pd.isna(roi_id_local):
            hits = masks_4d.flatten() == v
            if np.any(hits):
                rgba = layer.get_color(v)
                rgba = [round(r * 255) for r in rgba]
                rgba[3] = layer.opacity * 256
                rois.append(save_label(masks_4d == v, image, rgba))
        else:
            return []
    return rois


def save_label(bool_4d: np.ndarray, image: ImageWrapper, rgba) -> RoiI:
    """Turns a boolean array of shape (t, z, y, x) into OMERO Roi."""
    size_t = bool_4d.shape[0]
    size_z = bool_4d.shape[1]
    # Create an ROI with a shape for each Z/T that has some mask
    mask_shapes = []
    for z in range(0, size_z):
        for t in range(0, size_t):
            masks_2d = bool_4d[t][z]
            if np.any(masks_2d.flatten()):
                mask = mask_from_binary_image(masks_2d, rgba=rgba, z=z, t=t)
                mask_shapes.append(mask)

    return create_roi(image, mask_shapes)
