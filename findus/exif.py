from PIL import Image
from PIL.ExifTags import TAGS
from PIL.ExifTags import GPSTAGS
from shapely.geometry import Point
import pandas as pd
import geopandas as gpd
import os

from findus.geo import get_coordinates


class ExifHandler():
    def load_exif(self, filepath):
        image = Image.open(filepath)
        image.verify()
        self.exif = image._getexif()

    def get_labeled_exif(self):
        labeled = {}
        for (key, val) in self.exif.items():
            labeled[TAGS.get(key)] = val
        return labeled

    def get_geotagging(self):
        if not self.exif:
            raise ValueError("No EXIF metadata found")

        geotagging = {}
        for (idx, tag) in TAGS.items():
            if tag == 'GPSInfo':
                if idx not in self.exif:
                    raise ValueError("No EXIF geotagging found")

                for (key, val) in GPSTAGS.items():
                    if key in self.exif[idx]:
                        geotagging[val] = self.exif[idx][key]
        return geotagging


def exif_to_geodataframe(photo_directory,
                         crs,
                         photo_format='.jpeg'):
    points = []
    paths = []
    gps_directions = []
    for file in os.listdir(photo_directory):
        if file.endswith(photo_format):
            path = os.path.join(photo_directory, file)
            try:
                exif = ExifHandler()
                exif.load_exif(path)
                geotags = exif.get_geotagging()
                coordinates = get_coordinates(geotags)
                gps_directions.append(float(geotags['GPSImgDirection']))
                points.append(Point(coordinates))
                paths.append(path)
            except:
                print('Skipping file ' + file)

    data = pd.DataFrame(list(zip(paths, gps_directions)), columns=['path', 'direction'])
    sample_df = gpd.GeoDataFrame(data, crs=crs, geometry=points)
    return sample_df
