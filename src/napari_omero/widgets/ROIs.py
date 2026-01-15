import warnings

import napari.viewer
from magicgui.widgets import Container, PushButton, create_widget
from napari.layers import Image, Labels
from napari.utils.notifications import show_info

from napari_omero.plugins.loaders import load_rois
from napari_omero.plugins.omero import save_rois
from napari_omero.utils import lookup_obj
from napari_omero.widgets.gateway import QGateWay
from omero.cli import ProxyStringType


def omero_roi_manager() -> Container:
    """A widget to manage ROIs between napari and OMERO.

    This widget handles both loading ROI from OMERO, as well as saving
    napari annotations to OMERO as ROI.
    """
    omero_image_combobox = create_widget(label="OMERO Image", annotation=Image)
    load_button = PushButton(text="Load Annotations from OMERO")
    save_button = PushButton(text="Upload Annotations to OMERO")

    @load_button.clicked.connect
    def _load_rois_from_omero() -> None:
        viewer = napari.viewer.current_viewer()
        image_layer = omero_image_combobox.value

        if not image_layer or "omero" not in image_layer.metadata:
            show_info("No OMERO metadata found in selected layer.")
            return

        gateway = QGateWay()
        layer_name = image_layer.name
        img_id = int(layer_name.split(":")[0])

        image_wrapper = gateway.conn.getObject("Image", img_id)
        points_coords, points_meta, _ = load_rois(
            gateway.conn, image_wrapper, load_points=True
        )[0]
        shapes_coords, shapes_meta, _ = load_rois(
            gateway.conn, image_wrapper, load_points=False
        )[0]

        if points_meta is None and shapes_meta is None:
            show_info(f"No ROIs or points found for OMERO image id {img_id}.")
            return
        

        if shapes_meta:
            if shapes_meta["name"] not in viewer.layers:
                viewer.add_shapes(shapes_coords, **shapes_meta)
            else:
                update_local_layer(
                    incoming_layer=(shapes_coords, shapes_meta, 'shapes'),
                    existing_layer=viewer.layers[shapes_meta["name"]]
                    )
        if points_meta:
            if points_meta["name"] not in viewer.layers:
                viewer.add_points(points_coords, **points_meta, feature_defaults=feature_defaults)
            else:
                update_local_layer(
                    incoming_layer=(points_coords, points_meta, 'points'),
                    existing_layer=viewer.layers[points_meta["name"]]
                    )


    @save_button.clicked.connect
    def _save_rois_to_omero() -> None:
        omero_image = omero_image_combobox.value
        # check if 'omero' field is in metadata
        if not omero_image or "omero" not in omero_image.metadata:
            warnings.warn("No OMERO metadata found in selected layer.", stacklevel=2)
            return

        # assert that layer is 4D if it is a labels layer
        if isinstance(omero_image, Labels) and omero_image.ndim != 4:
            raise ValueError(
                "Labels layer must be 4D (time, z, y, x) to be uploaded to OMERO."
            )

        gateway = QGateWay()
        image_id = omero_image.metadata["omero"]["@id"]

        image_wrapper = lookup_obj(
            gateway.conn, ProxyStringType("Image")(f"Image:{image_id}")
        )

        viewer = napari.viewer.current_viewer()
        save_rois(viewer=viewer, image=image_wrapper)

        trg = image_wrapper.getName()
        show_info(f"All annotation layers uploaded to OMERO image id {image_id}: {trg}")

    container = Container(widgets=[omero_image_combobox, load_button, save_button])
    return container

def update_local_layer(
        incoming_layer: "napari.types.LayerDataTuple",
        existing_layer: "napari.layers.Layer",) -> None:
    """Compare two napari layers and update existing layer if different."""
    import pandas as pd

    # Check for ROI ids that have been removed on the remote but are still
    # present in the existing layer
    removed_rois_idx = [
        idx for idx, roi in enumerate(existing_layer.features['shape_id'].values)
        if roi not in incoming_layer[1]['features']['shape_id']
        ]
    
    if removed_rois_idx:
        existing_layer.selected_data = set(removed_rois_idx)
        existing_layer.remove_selected()

    # Now, check for ROI ids that have been added on the remote but are not
    # present in the existing layer
    added_rois_idxs = [
        idx for idx, roi in enumerate(incoming_layer[1]['features']['shape_id'])
        if roi not in existing_layer.features['shape_id'].values
        ]
    
    if added_rois_idxs:
        for roi_idx in added_rois_idxs:
            new_data = incoming_layer[0][roi_idx]
            existing_layer.add(
                new_data,
                shape_type=incoming_layer[1]['shape_type'][roi_idx],
                edge_width=incoming_layer[1]['edge_width'][roi_idx],
                edge_color=incoming_layer[1]['edge_color'][roi_idx],
                face_color=incoming_layer[1]['face_color'][roi_idx],)

            for key in incoming_layer[1]['features'].keys():
                existing_layer.features.loc[
                    len(existing_layer.data) - 1, key
                    ] = incoming_layer[1]['features'][key][roi_idx]


    show_info(f"ROI layer already exists locally.\nAdded {len(added_rois_idxs)} ROIs, removed {len(removed_rois_idx)} ROIs.")