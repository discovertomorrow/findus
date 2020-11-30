import findus.sampling.crop_photo_sampling as fis
import numpy as np

from shapely.geometry import box

from sentinelsat import SentinelAPI
from dataclasses import dataclass
import json
import datetime
from tqdm import tqdm
import os
import zipfile
import enum
import geopandas as gpd
from rasterio.mask import mask
import re
import rasterio
from scipy.ndimage import zoom
from skimage.segmentation import felzenszwalb, mark_boundaries, slic


@dataclass
class Sentinel2Specs:
    band_resolution = {'B02': ('R10m', 10),
                       'B03': ('R10m', 10),
                       'B04': ('R10m', 10),
                       'B08': ('R10m', 10),
                       'B11': ('R20m', 20),
                       'SCL': ('R20m', 20)}


def get_product_band_paths(product_path,
                           import_bands=['B02', 'B03', 'B04', 'B08', 'B11', 'SCL']):
    product_name = os.listdir(os.path.join(product_path, 'GRANULE'))[0]
    image_directory = os.path.join(
        product_path, 'GRANULE', product_name, 'IMG_DATA/')

    band_paths = list()

    for band in import_bands:
        band_directory = os.path.join(
            image_directory, Sentinel2Specs.band_resolution[band][0])
        filename = [f for f in os.listdir(band_directory) if band in f][0]
        band_paths.append(os.path.join(band_directory, filename))
    return band_paths


def get_json_bounds(gdf):
    return [json.loads(gdf.to_json())['features'][0]['geometry']]


def get_product_info_from_name(product_name):
    tile_id = re.search(r'_([A-Z]\d{2}[A-Z]{3})_', product_name).group(1)
    return tile_id


def scene_classification_to_binary_mask(scene_classification_image,
                                        target_classes=[0, 7, 8, 9, 10, 11]):
    mask = np.ones(scene_classification_image.shape)
    mask[np.isin(scene_classification_image, target_classes)] = np.nan
    return mask


def get_array_from_product(path):
    file = rasterio.open(path, driver='JP2OpenJPEG')
    img = file.read(1)
    return img, file.meta


class AOI:
    def __init__(self,
                 bounds,
                 name,
                 base_directory,
                 copernicus_credentials,
                 crs='EPSG:32632',
                 target_bands=None):

        self.target_bands = target_bands
        self.crs = crs
        self.original_bounds = bounds
        self.aoi = gpd.GeoDataFrame(
            {'AOI': ['GRF'], 'geometry': [bounds]}, crs='EPSG:4326').to_crs(self.crs)
        self.name = name
        self.base_directory = base_directory
        self.copernicus_credentials = copernicus_credentials

        self.hub = SentinelAPI(self.copernicus_credentials.username,
                               self.copernicus_credentials.password,
                               'https://scihub.copernicus.eu/dhus')

        self.raw_data_directory = os.path.join(
            self.base_directory, self.name, 'Data/Raw/')
        self.processed_data_directory = os.path.join(
            self.base_directory, self.name, 'Data/Processed/')
        self.results_directory = os.path.join(
            self.base_directory, self.name, 'Results/')

        self.raw_data_paths = None

        if not os.path.isdir(self.raw_data_directory):
            os.makedirs(self.raw_data_directory)
        if not os.path.isdir(self.processed_data_directory):
            os.makedirs(self.processed_data_directory)
        if not os.path.isdir(self.results_directory):
            os.makedirs(self.results_directory)

    @property
    def bounds(self):
        return self.aoi.geometry[0]

    def request_data(self,
                     min_date,
                     max_date,
                     platformname='Sentinel-2',
                     processinglevel='Level-2A'):
        self.available_products = self.hub.to_geodataframe(self.hub.query(self.original_bounds,
                                                                          date=(
                                                                              min_date, max_date),
                                                                          platformname=platformname,
                                                                          processinglevel=processinglevel))

    def download_data(self,
                      num_images=1):

        self.available_products = self.available_products.sort_values(by='cloudcoverpercentage')

        print('Start downloading data from Copernicus')
        for i in tqdm(range(min(num_images, len(self.available_products)))):
            self.hub.download(self.available_products.index[i], self.raw_data_directory)
        print('Finished data download.')

        print('Unzipping downloaded data.')
        self.raw_data_paths = []
        for file in tqdm(os.listdir(self.raw_data_directory)):
            file_path = os.path.join(self.raw_data_directory, file)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(self.raw_data_directory)
            self.raw_data_paths.append(file_path.replace('.zip', '') + '.SAFE')
            os.remove(file_path)

    def process_raw_product(self,
                            path,
                            import_bands=['B02', 'B03', 'B04', 'B08', 'B11', 'SCL']):

        self.target_bands = [b for b in import_bands if b != 'SCL']
        product_name = re.search(r'Raw/(.*).SAFE', path).group(1)
        export_directory = os.path.join(
            self.processed_data_directory, product_name)
        if not os.path.isdir(export_directory):
            os.makedirs(export_directory)

        band_paths = get_product_band_paths(product_path=path,
                                            import_bands=import_bands)

        for p, b in zip(band_paths, import_bands):

            band = rasterio.open(p, driver='JP2OpenJPEG')
            out_img, out_transform = mask(
                dataset=band, shapes=get_json_bounds(self.aoi), crop=True)

            out_meta = band.meta.copy()

            out_meta.update({"driver": "JP2OpenJPEG",
                             "height": out_img.shape[1],
                             "width": out_img.shape[2],
                             "transform": out_transform})

            export_path = os.path.join(export_directory, b + '.jp2')
            with rasterio.open(export_path, "w", **out_meta) as dest:
                dest.write(out_img)

    def start_raw_product_processing(self,
                                     import_bands=['B02', 'B03', 'B04', 'B08', 'B11', 'SCL']):
        print("Start processing of raw products.")
        for p in tqdm(os.listdir(self.raw_data_directory)):
            self.process_raw_product(path=os.path.join(
                self.raw_data_directory, p), import_bands=import_bands)

    def combine_processed_products(self, combination_function=np.nanmean):
        masked_imgs = {k: [] for k in self.target_bands}

        processed_products = os.listdir(self.processed_data_directory)
        for prod in processed_products:
            directory = os.path.join(self.processed_data_directory, prod)

            # Read images
            product_images = dict()
            for file in os.listdir(directory):
                path = os.path.join(directory, file)
                img, meta = get_array_from_product(path)

                product_images['meta'] = meta
                product_images[file.replace('.jp2', '')] = img

            # Combine into masked numpy array
            scene_classification = zoom(product_images['SCL'], zoom=2, order=0)
            mask = scene_classification_to_binary_mask(scene_classification)

            for key, item in product_images.items():

                if key == 'SCL' or key == 'meta':
                    continue
                else:
                    if Sentinel2Specs.band_resolution[key][1] == 20:
                        item = zoom(item, zoom=2, order=0)
                    masked_band = np.multiply(item, mask[:item.shape[0], :item.shape[1]])  # TODO Fix alignment
                    masked_imgs[key].append(masked_band)

            # Combine images
            self.combined_imgs = dict()
            for key in masked_imgs.keys():
                self.combined_imgs[key] = combination_function(np.array(masked_imgs[key]), axis=0)
            self.combined_imgs['meta'] = meta

    def perform_image_segmentation(self,
                                   n_segments=500,
                                   compactness=15,
                                   band='B02'):
        # TODO extent for multi band segmentation
        image = self.combined_imgs[band]
        image[np.isnan(image)] = 0
        segments = slic(image=image, n_segments=n_segments, compactness=compactness)
        self.segments = segments
        segments = segments.astype('uint32')
        segments = np.expand_dims(segments, 0)

        segments_meta = self.combined_imgs['meta']
        segments_meta['width'] = segments.shape[2]
        segments_meta['height'] = segments.shape[1]
        segments_meta['dtype'] = segments.dtype.name
        segments_meta['driver'] = 'GTiff'

        export_path = os.path.join(self.results_directory, 'segments.tif')
        with rasterio.open(export_path, "w", **segments_meta) as dest:
            dest.write(segments)
