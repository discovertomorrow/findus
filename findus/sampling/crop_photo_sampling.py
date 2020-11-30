import rasterio
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from shapely.geometry import shape, Point, Polygon

from findus.exif import ExifHandler
from findus.geo import get_coordinates
from findus.plantnet import query_plant_classification


class CropPhotoSamples():
    def __init__(self, init_path=None, crs='EPSG:4326', plant_net_credentials=None):
        if init_path is not None:
            self.samples = gpd.read_file(init_path)
            self.init_path = init_path
        else:
            self.samples = None
            self.init_path = None
        self.crs = rasterio.crs.CRS.from_dict(init=crs)
        self.plant_net_credentials = plant_net_credentials

    @property
    def max_sample_id(self):
        if self.samples is None:
            return 0
        else:
            return max(self.samples.sampleID)

    def to_crs(self, crs='EPSG:32632'):
        self.crs = crs
        if self.samples is not None:
            self.samples = self.samples.to_crs(crs)

    def add_samples(self, photo_directory):
        points = []
        paths = []
        filenames = []
        gps_directions = []
        dates = []

        new_sample_id = self.max_sample_id + 1

        for file in os.listdir(photo_directory):
            if file.endswith('.jpeg'):
                path = os.path.join(photo_directory, file)
                try:
                    exif = ExifHandler()
                    exif.load_exif(path)
                    geotags = exif.get_geotagging()
                    coordinates = get_coordinates(geotags)
                    gps_directions.append(float(geotags['GPSImgDirection']))
                    dates.append(geotags['GPSDateStamp'])
                    points.append(Point(coordinates))
                    paths.append(path)
                    filenames.append(os.path.basename(path))
                except:
                    print('Skipping file ' + file)

        data = pd.DataFrame(list(zip(paths, filenames, dates, gps_directions)),
                            columns=['path', 'filename', 'date', 'direction'])
        data['classification_tag_1'] = None
        data['classification_score_1'] = None
        data['classification_tag_2'] = None
        data['classification_score_2'] = None
        data['classification_tag_3'] = None
        data['classification_score_3'] = None
        new_samples = gpd.GeoDataFrame(data, crs=self.crs, geometry=points)

        if self.samples is None:
            new_samples['sampleID'] = np.arange(new_sample_id, len(new_samples) + 1)
            self.samples = new_samples
        else:
            # Remove duplicate filenames
            for idx, row in new_samples.iterrows():
                if any(self.samples.filename.str.contains(row['filename'])):
                    print('Dropping duplicate file ' + row['filename'])
                    new_samples = new_samples.drop(idx, axis=0)
            new_samples['sampleID'] = np.arange(new_sample_id, len(new_samples) + 1)
            self.samples = self.samples.append(new_samples)

        return self

    def save_samples(self, saving_path=None):
        if saving_path is None:
            if self.init_path is not None:
                saving_path = self.init_path
            else:
                raise ValueError('Please specify saving path.')
        self.samples.to_file(saving_path, driver='GeoJSON')

    def classify_samples(self, classification_indices=None):

        if self.plant_net_credentials == None:
            raise ValueError('A PlantNet API key must be supplied for photo classification.')

        if classification_indices is None:
            classification_indices = self.samples.index[self.samples['classification_tag_1'].apply(pd.isnull)]

        print('Start classifying image samples via PlantNet API.')

        for i in tqdm(classification_indices):
            try:
                dir_image = self.samples.loc[i]['path']

                classification_results = query_plant_classification(dir_image, self.plant_net_credentials.key)

                desc = 'scientificNameWithoutAuthor'
                self.samples.loc[i, 'classification_tag_1'] = classification_results['results'][0]['species'][desc]
                self.samples.loc[i, 'classification_score_1'] = classification_results['results'][0]['score']
                self.samples.loc[i, 'classification_tag_2'] = classification_results['results'][1]['species'][desc]
                self.samples.loc[i, 'classification_score_2'] = classification_results['results'][1]['score']
                self.samples.loc[i, 'classification_tag_3'] = classification_results['results'][2]['species'][desc]
                self.samples.loc[i, 'classification_score_3'] = classification_results['results'][2]['score']
            except:
                print('Failed to process ' + dir_image)
                if 'error' in classification_results.keys():
                    print(classification_results['message'])
                print('Stopping photo classification due to request error.')
                break
