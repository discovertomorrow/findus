import requests
import json

def query_plant_classification(image_path,
                               api_key,
                               organ='leaf'):
    
    url = 'https://my-api.plantnet.org/v2/identify/all?api-key=' + api_key
    data = {'organs': organ}
    files = {'images': open(image_path, 'rb')}
    
    classification_str = requests.post(url, data=data, files=files)
    classification_results = json.loads(classification_str.text)
    
    return classification_results