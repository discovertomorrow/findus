import rasterio
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import shape


class FieldSamples():
    def __init__(self,
                 init_path=None,
                 crs='EPSG:4326'):
        if init_path is not None:
            self.samples = gpd.read_file(init_path)
            self.init_path = init_path
        else:
            self.samples = None
            self.init_path = None
        self.crs = rasterio.crs.CRS.from_dict(init=crs)

    def add_samples(self,
                    crop_photo_samples,
                    path_segments,
                    minimum_classification_score=0.3):
        segments_raster = rasterio.open(path_segments)
        segments = segments_raster.read(1)

        geometries = []
        crops = []
        scores = []

        for i, f in crop_photo_samples.samples.iterrows():
            if f['classification_score_1'] is None or float(f['classification_score_1']) < minimum_classification_score:
                print('Skipping index ' + str(i) + ' due to missing or too low classification score')
            else:
                x, y = f['geometry'].coords.xy
                segment_id = segments[segments_raster.index(x, y)]
                segment = np.where(segments == segment_id, 1, 0)
                shapes = []
                for shp, _ in rasterio.features.shapes(segment.astype('int16'), transform=segments_raster.transform):
                    shapes.append(shp)
                segment_boundaries = shape(shapes[0])
                geometries.append(segment_boundaries)
                crops.append(f['classification_tag_1'])
                scores.append(float(f['classification_score_1']))

        data = pd.DataFrame(list(zip(crops, scores)), columns=['crop', 'score'])
        new_samples = gpd.GeoDataFrame(data, crs=crop_photo_samples.crs, geometry=geometries)

        if self.samples is None:
            self.samples = new_samples
        else:
            self.samples = self.samples.append(new_samples)
        return self

    def save_samples(self, saving_path=None):
        if saving_path is None:
            if self.init_path is not None:
                saving_path = self.init_path
            else:
                raise ValueError('Please specify saving path.')
        self.samples.to_file(saving_path, driver='GeoJSON')

    def plot(self,
             background_image=None,
             background_transform=None,
             saving_path=None):
        fig, ax = plt.subplots(1, 1, figsize=(15, 10))
        if background_image is None:
            self.samples.plot(ax=ax, column='crop', legend=True)
        else:
            rasterio.plot.show(background_image, ax=ax, transform=background_transform, alpha=1, cmap='gray')
            self.samples.plot(ax=ax, column='crop', legend=True, alpha=0.7)
        if saving_path is not None:
            plt.savefig(saving_path)
