import sys
from functools import wraps

import napari
import numpy
from napari.layers.labels.labels import Labels as labels_layer
from napari.layers.points.points import Points as points_layer
from napari.layers.shapes.shapes import Shapes as shapes_layer
from qtpy.QtWidgets import QPushButton

import omero.clients
from napari_omero.utils import lookup_obj, obj_to_proxy_string
from omero.cli import CLI, BaseControl, ProxyStringType
from omero.gateway import BlitzGateway, PixelsWrapper

from .writers import (
    save_labels,
    create_omero_point,
    create_omero_shape,
    create_roi
    )

HELP = "Connect OMERO to the napari image viewer"

VIEW_HELP = "Usage: omero napari view Image:1"


def gateway_required(func):
    """Decorator which initializes a client and BlitzGateway.

    makes sure that all services of the Blitzgateway are closed again.
    """

    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        self.client = self.ctx.conn(*args)
        self.gateway = BlitzGateway(client_obj=self.client)
        try:
            return func(self, *args, **kwargs)
        finally:
            if self.gateway is not None:
                self.gateway.close(hard=False)
                self.gateway = None
                self.client = None

    return _wrapper


class NapariControl(BaseControl):
    gateway = None
    client = None

    def _configure(self, parser):
        parser.add_login_arguments()
        sub = parser.sub()
        view = parser.add(sub, self.view, VIEW_HELP)

        obj_type = ProxyStringType("Image")

        view.add_argument("object", type=obj_type, help="Object to view")
        view.add_argument(
            "--eager",
            action="store_true",
            help=(
                "Use eager loading to load all planes immediately instead"
                "of lazy-loading each plane when needed"
            ),
        )

    @gateway_required
    def view(self, args):
        if isinstance(args.object, ImageI):
            try:
                img = lookup_obj(self.gateway, args.object)
            except NameError:
                self.ctx.die(110, f"No such {type}: {args.object.id}")

            self.ctx.out(f"View image: {img.name}")

            viewer = napari.Viewer()  # type: ignore

            add_buttons(viewer, img)

            viewer.open(
                f"omero://{obj_to_proxy_string(args.object)}",
                plugin="napari-omero",
            )
            set_dims_defaults(viewer, img)
            set_dims_labels(viewer, img)

            # add 'conn' and 'omero_image' to the viewer console
            viewer.update_console({"conn": self.gateway, "omero_image": img})
            napari.run()  # type: ignore


def add_buttons(viewer, img):
    """Add custom buttons to the viewer UI."""

    def handle_save_rois():
        save_rois(viewer, img)

    button = QPushButton("Save ROIs to OMERO")
    button.clicked.connect(handle_save_rois)
    viewer.window.add_dock_widget(button, name="Save OMERO", area="left")


def get_data(img, c=0):
    """
    Get 4D numpy array of pixel data, shape = (size_t, size_z, size_y, size_x).

    :param  img:        omero.gateway.ImageWrapper
    :c      int:        Channel index
    """
    size_z = img.getSizeZ()
    size_t = img.getSizeT()
    # get all planes we need in a single generator
    zct_list = [(z, c, t) for t in range(size_t) for z in range(size_z)]
    pixels = img.getPrimaryPixels()
    plane_gen = pixels.getPlanes(zct_list)

    t_stacks = []
    for _ in range(size_t):
        z_stack = [next(plane_gen) for _ in range(size_z)]
        t_stacks.append(numpy.array(z_stack))
    return numpy.array(t_stacks)


def set_dims_labels(viewer, image):
    """Set labels on napari viewer dims, based on dimensions of OMERO image.

    :param  viewer:     napari viewer instance
    :param  image:      omero.gateway.ImageWrapper
    """
    # dims (t, z, y, x) for 5D image
    dims = "TZ"

    for idx, label in enumerate(dims):
        viewer.dims.set_axis_label(idx, label)


def set_dims_defaults(viewer, image):
    """Set default Z/T index on napari viewer.

    Set Z/T slider index on napari viewer, according
    to default Z/T indecies of the OMERO image.

    :param  viewer:     napari viewer instance
    :param  image:      omero.gateway.ImageWrapper
    """
    # dims (t, z, y, x) for 5D image
    if image.getSizeT() > 1:
        viewer.dims.set_point(0, image.getDefaultT())
    if image.getSizeZ() > 1:
        viewer.dims.set_point(1, image.getDefaultZ())


def save_rois(
        viewer,
        image,
        mode: str = "Update"
    ) -> None:
    """Save napari ROIs to OMERO.

    Usage: In napari, open console...
    >>> from napari_omero import *
    >>> save_rois(viewer, omero_image).
    """
    import pandas as pd
    conn = image._conn
    group_id = image.getDetails().getGroup().getId()
    conn.SERVICE_OPTS.setOmeroGroup(group_id)

    # Check if there are existing ROIs on the remote
    # that do not exist locally and remove them on the remote
    roi_service = conn.getRoiService()
    roi_ids = roi_service.findByImage(image.getId(), None).rois

    # Loop through all ROIs:
    # We need to know what ROIs/shapes already exist on the remote
    remote_roi_ids = []
    remote_shape_ids = []

    for roi in roi_ids:
        roi_id = roi.getId().getValue()
        # Loop through all shapes in each ROI
        for shape in roi.copyShapes():
            shape_id = shape.getId().getValue()
            remote_shape_ids.append(shape_id)
            remote_roi_ids.append(roi_id)

    for layer in viewer.layers:
        if type(layer) is points_layer:
            for idx, p in enumerate(layer.data):

                # Check if ROI already has an OMERO id
                # If it has one, it already exists on the remote
                roi_id_local = layer.features.iloc[idx]["roi_id"]
                shape_id_local = layer.features.iloc[idx]["shape_id"]
                if pd.isna(shape_id_local) and pd.isna(roi_id_local):
                    point = create_omero_point(p)
                    roi = create_roi(image, [point])
                    print(f"Created ROI: {roi.id.val}")

            # remove any remote shapes that are not present locally
            # TODO: Add a safeguard here that prevents deleting all remote shapes
            shape_ids = [s for s in remote_shape_ids if not s in layer.features['shape_id'].values]
            if shape_ids:
                conn.deleteObjects("Shape", shape_ids)
                
        elif type(layer) is shapes_layer:
            if len(layer.data) == 0 or len(layer.shape_type) == 0:
                continue
            shape_types = layer.shape_type
            if isinstance(shape_types, str):
                shape_types = [layer.shape_type for _ in range(len(layer.data))]
            for idx, (shape_type, data) in enumerate(zip(shape_types, layer.data)):

                # Check if ROI already has an OMERO id
                # If it has one, it already exists on the remote
                roi_id_local = layer.features.iloc[idx]["roi_id"]
                shape_id_local = layer.features.iloc[idx]["shape_id"]
                if pd.isna(shape_id_local) and pd.isna(roi_id_local):
                    shape = create_omero_shape(shape_type, data)
                    if shape is not None:
                        roi = create_roi(image, [shape])
                        print(f"Created ROI: {roi.id.val}")

            # remove any remote shapes that are not present locally
            # TODO: Add a safeguard here that prevents deleting all remote shapes
            shape_ids = [s for s in remote_shape_ids if not s in layer.features['shape_id'].values]
            if shape_ids:
                conn.deleteObjects("Shape", shape_ids)

        elif type(layer) is labels_layer:
            print("Saving Labels...")
            save_labels(layer, image)


class NonCachedPixelsWrapper(PixelsWrapper):
    """Extend gateway.PixelWrapper to override _prepareRawPixelsStore."""

    def _prepareRawPixelsStore(self):
        """
        Creates RawPixelsStore and sets the id etc.

        This overrides the superclass behaviour to make sure that
        we don't re-use RawPixelStore in multiple processes since
        the Store may be closed in 1 process while still needed elsewhere.
        This is needed when napari requests may planes simultaneously,
        e.g. when switching to 3D view.
        """
        ps = self._conn.c.sf.createRawPixelsStore()
        ps.setPixelsId(self._obj.id.val, True, self._conn.SERVICE_OPTS)
        return ps


omero.gateway.PixelsWrapper = NonCachedPixelsWrapper
# Update the BlitzGateway to use our NonCachedPixelsWrapper
omero.gateway.refreshWrappers()


if __name__ == "__main__":
    # Register napari_omero as an OMERO CLI plugin
    cli = CLI()
    cli.register("napari", NapariControl, HELP)
    cli.invoke(sys.argv[1:])
