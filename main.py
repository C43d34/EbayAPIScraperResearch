# import pandas as pd
import os 
import requests
import json

# from ebayAPI import API_KEY
from ebayAPI import AUTH_TOKEN

BROWSE_API_BASE = "https://api.ebay.com/buy/browse/v1/item_summary/search?"
SEARCH_PARAMS = {
    "q": { #keyswords concatenated into a string => 
        "AND": [], #"k1 k2" space separated means k1 AND k2
        "OR": [] #"(k1, k2, ...)" comma separated means k1 OR k2 or ... 
                    #could possibly get fancy with OR and AND by having OR be conditionally placed between AND search parameters so we can search for (X or Y) and (A or B)
                    # => "(x, y) (a, b)" is how it would look in url I think
                    #current structing of URL with OR params will just be passed all at once so this conceptual functionality isn't possibly yet. 
        },              
    "filter": [], #different filters with each their own formatting => {filter1: params}, {filter2: params}
    "sort": "", #sort=price from lowest to highest price (maybe behave strangely with bidding items which I need to look)
    "limit": "", #number of items to return per page (max 200, default 50)
    "offset": "" #specifies number of items to skip in result set (control pagination of the output) 
}

#Perform a search (browse) request through ebay API.
    #Returns:
    # 1. status code of response (-1 if unexpected error)
    # 2. dictionary object of the raw response
def getSearchResult(request_payload):
    response_status = 0
    response_parsed = {}
    try:
    #Make REST request 
        #Specifies auth token and request headers
        headers = {
            "Authorization": "Bearer " + AUTH_TOKEN,
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "X-EBAY-C-ENDUSERCTX": "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>"
        }
    #(DEBUGGING) test request 
        # response = requests.get('https://api.ebay.com/buy/browse/v1/item_summary/search?q=drone&limit=1&filter=price:[300..800],priceCurrency:USD,conditions:{NEW}', headers = headers )

        response = requests.get(buildSearchURL(BROWSE_API_BASE, request_payload), headers = headers)
        response_status = response.status_code
        response_parsed = response.json()

    #(DEBUGGING) dump response to a json file 
        f = open("new.json", 'w')
        json.dump(response_parsed, f, indent = 4)

#Catch exception
    except requests.exceptions.HTTPError as e:
        print(e)
        print(e.response.dict())
        response_status = -1

#Return result of the search request
    return response_status, response_parsed



#Puts together a url for REST GET request relative to ebay API search params
    #expect api_base_url in string format
    #expects api_params in dict format


def buildSearchURL(api_base_url, api_params):
    params_substring_list = []
    for key in api_params.keys(): 
        if (key == "q"):
            params_substring = key + "="
            
            list_keywords_to_include_overall = api_params[key]["AND"]
            if (len(list_keywords_to_include_overall) > 0):
                params_substring += " ".join(list_keywords_to_include_overall)

            list_keywords_to_include_as_any = api_params[key]["OR"]
            if (len(list_keywords_to_include_as_any) > 0): 
                params_substring += " (" + ", ".join(list_keywords_to_include_as_any) + ")"

            params_substring_list.append(params_substring)


    return api_base_url + "&".join(params_substring_list)

# getSearchResult("")

#(DEBUGGING) TEST BUILD SEARCH URL THINGY
print(buildSearchURL(BROWSE_API_BASE, {"q": {"AND":["thing1", "thing2"], "OR":["waz"]}}))


