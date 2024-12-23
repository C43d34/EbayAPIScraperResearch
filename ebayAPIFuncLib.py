# import pandas as pd
import os
import urllib.parse 
import requests
import json
import urllib
import base64
from datetime import datetime, timedelta


# from ebayAPI import API_KEY
from ebayAPI import getAUTHTOKEN, getCLIENTID, getCLIENTSECRET, getCONTEXTLOCATION, getTOKENEXPIREDATE, setAUTHTOKEN, setTOKENEXPIREDATE


BROWSE_SUMMARY_API_BASE = "https://api.ebay.com/buy/browse/v1/item_summary/search?"
# HISTORICAL_INSIGHT_API_BASE = "https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search?"
BROWSE_SPECIFIC_ITEM_API_BASE = "https://api.ebay.com/buy/browse/v1/item/"
CLIENT_CREDENTIALS_AUTH_FLOW_BASE = "https://api.ebay.com/identity/v1/oauth2/token"

SEARCH_PARAMS = {
    "q": { #keyswords concatenated into a string => 
        "AND": [], #"k1 k2" space separated means k1 AND k2
        "OR": [] #"(k1, k2, ...)" comma separated means k1 OR k2 or ... 
                    #could possibly get fancy with OR and AND by having OR be conditionally placed between AND search parameters so we can search for (X or Y) and (A or B)
                    # => "(x, y) (a, b)" is how it would look in url I think
                    #current structing of URL with OR params will just be passed all at once so this conceptual functionality isn't possibly yet. 
        },              
    "filter": {}, #different filters with each their own formatting => {filter1: params}, {filter2: params}
    # "sort": "", #sort=price from lowest to highest price (maybe behave strangely with bidding items which I need to look)
                    #(TODO required to be url encoded according to documentation)
    "limit": "", #number of items to return per page (max 200, default 50)
    "offset": "" #specifies number of items to skip in result set (control pagination of the output) 
}

def util_APIFromRawURL(url: str, log_output = False, log_output_path = "last_api_response_debug.json"):
    '''
    Make a request through a direct URL link
        Uses headers specific to EBAY browse api standards 
    
    '''
    try:
        _checkAuthToken()
    except requests.exceptions.HTTPError as e:
        print("error checking authentication token")
        print(e)
        return

    try:
        headers = {
            "Authorization": "Bearer " + getAUTHTOKEN(),
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "X-EBAY-C-ENDUSERCTX": "contextualLocation=" + urllib.parse.quote_plus(getCONTEXTLOCATION())
        }

        response = requests.get(url, headers = headers)
        response_parsed = response.json()
        
    #(DEBUGGING) dump response to a json file 
        if (log_output):
            f = open(log_output_path, 'w') 
            json.dump(response_parsed, f, indent = 4)

        if(response.status_code != 200):
            util_HandleUnsuccessfulStatus(response.status_code, response_parsed)
#Catch exception
    except requests.exceptions.HTTPError as e:
        print(e)
        print(e.response.dict())
    return
 


def util_CompileSalePriceStatsOfSearchResults(list_of_items: list) -> tuple[float, float, float]:
    '''
    Calcualtes the min, max, and average price among a list of items 
        Expects the list formatted in json from a generic getSearchResults call 
    Returns
        min_price, max_price, avg_price
    '''

    prices = []
    for item in list_of_items:
        direct_price = float(item["price"]["value"])
        shipping_price = 0 
        if ("shippingOptions" in item):
            shipping_price = float(item["shippingOptions"][0]["shippingCost"]["value"] if "shippingCost" in item["shippingOptions"][0].keys() else 0.0)
        
        prices.append(direct_price + shipping_price)

    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)

    return min_price, max_price, avg_price



def util_HandleUnsuccessfulStatus(status_code: int, response_details: json):
    match status_code:
        case 401: 
            if (response_details["message"] == 'Invalid access token'):
                print("Invalid access token to make EBAY request\n(Try calling getAppAuthToken())")

    return



def getSearchResults(request_payload: dict, log_url = False, log_output = False, log_output_path = "last_api_response_debug.json") -> tuple[int, dict]:
    '''
    Perform a search (browse) request through ebay API.
    
    Returns
        1. status code of response (-1 if unexpected error)
        2. dictionary object of the raw response
    '''
    try:
        _checkAuthToken()
    except requests.exceptions.HTTPError as e:
        print("error checking authentication token")
        print(e)
        return


    response_status = 0
    response_parsed = {}
    try:
    #Make REST request 
        #Specifies auth token and request headers
        headers = {
            "Authorization": "Bearer " + getAUTHTOKEN(),
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "X-EBAY-C-ENDUSERCTX": "contextualLocation=" + urllib.parse.quote_plus(getCONTEXTLOCATION())
        }
    #(DEBUGGING) test request 
        # response = requests.get('https://api.ebay.com/buy/browse/v1/item_summary/search?q=drone&limit=1&filter=price:[300..800],priceCurrency:USD,conditions:{NEW}', headers = headers )

        #Send GET request as url
        get_url = buildSearchURL(BROWSE_SUMMARY_API_BASE, request_payload)
        if (log_url): print(get_url)

        response = requests.get(get_url, headers = headers)
        response_status = response.status_code
        response_parsed = response.json()

    #(DEBUGGING) dump response to a json file
        if (log_output):
            f = open(log_output_path, 'w') 
            json.dump(response_parsed, f, indent = 4)

        if(response.status_code != 200):
            util_HandleUnsuccessfulStatus(response.status_code, response_parsed)

#Catch exception
    except requests.exceptions.HTTPError as e:
        print(e)
        print(e.response.dict())
        response_status = -1

#Return result of the search request
    return response_status, response_parsed



def buildSearchURL(api_base_url: str, api_params: dict) -> str:
    '''
    Puts together a url for REST GET request relative to ebay API search params
        expect api_base_url in string format
        expects api_params in dict format
    '''
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

        elif (key == "filter"):
            filter_conditions = []
            params_substring = key + "="

            for filter_condition in api_params[key].keys():
                filter_conditions.append(filter_condition + ":" + api_params[key][filter_condition])

            params_substring += ",".join(filter_conditions)
            params_substring_list.append(params_substring)

        elif (key == "limit"):
            results_limit = int(api_params[key])
            if (results_limit > 200):
                results_limit = 200
            elif (results_limit < 0):
                results_limit = 0
        
            params_substring_list.append(key + "=" + str(results_limit))

        elif (key == "offset"):
            results_offset = int(api_params[key])
            if (results_offset > 9999):
                results_offset = 9999
            elif (results_offset < 0):
                results_offset = 0
        
            params_substring_list.append(key + "=" + str(results_offset))

    return api_base_url + "&".join(params_substring_list)



def getItemDetails(item_id_to_inspect: str, log_url = False,  log_output = False, log_output_path = "last_api_response_debug.json") -> tuple[int, dict]:
    '''
    Get specific details about an item based on it's item ID
        (Useful for getting standardized Brand & MPN (manufacturer's product number) of the item for later indexing)

    Returns a tuple
        0. response status
        1. raw json response
    '''
    try:
        _checkAuthToken()
    except requests.exceptions.HTTPError as e:
        print("error checking authentication token")
        print(e)
        return


    response_status = 0
    response_parsed = {}
    try:
    #Make REST request 
        #Specifies auth token and request headers
        headers = {
            "Authorization": "Bearer " + getAUTHTOKEN(),
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "X-EBAY-C-ENDUSERCTX": "contextualLocation=" + urllib.parse.quote_plus(getCONTEXTLOCATION())
        }
        #Send GET request as url
        # get_url = buildSearchURL(BROWSE_API_DETAILS, request_payload)
        # item_id_to_inspect = "v1|146114120951|0" #(DEBUGGING)
        get_url = BROWSE_SPECIFIC_ITEM_API_BASE + item_id_to_inspect
        if (log_url): print(get_url)

        response = requests.get(get_url, headers = headers)
        response_parsed = response.json()
        response_status = response.status_code

    #(DEBUGGING) dump response to a json file
        if (log_output): 
            f = open(log_output_path, 'w')
            json.dump(response_parsed, f, indent = 4)

        if(response.status_code != 200):
            util_HandleUnsuccessfulStatus(response.status_code, response_parsed)

#Catch exception
    except requests.exceptions.HTTPError as e:
        print(e)
        print(e.response.dict())
        response_status = -1

#Return result of the search request
    return response_status, response_parsed



def getNewAppAuthToken(log_output = False, log_output_path = "last_api_response_debug.json"):
    '''
    Current auth token scopes:
        "https://api.ebay.com/oauth/api_scope" 
    '''
    try:
        b64_encoded_oauth_credentials_as_bytes = base64.b64encode((getCLIENTID() + ":" + getCLIENTSECRET()).encode())
        b64_encoded_oauth_credentials_as_string = b64_encoded_oauth_credentials_as_bytes.decode()

        headers = {
            "Authorization": "Basic " + b64_encoded_oauth_credentials_as_string,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        body = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        response = requests.post(CLIENT_CREDENTIALS_AUTH_FLOW_BASE, headers = headers, data=urllib.parse.urlencode(body))
        response_parsed = response.json()

    #(DEBUGGING) dump response to a json file 
        if (log_output):
            f = open(log_output_path, 'w') 
            json.dump(response_parsed, f, indent = 4)

        if (response.status_code != 200):
            util_HandleUnsuccessfulStatus(response.status_code, response_parsed)
        else:
            setAUTHTOKEN(response_parsed["access_token"])
            setTOKENEXPIREDATE((datetime.now() + timedelta(seconds=float(response_parsed["expires_in"]))).timestamp())

#Catch exception
    except requests.exceptions.HTTPError as e:
        print(e)

    return


def _checkAuthToken():
    '''
    Checks expire date of current auth token, refreshes if it necessary. 
    '''
    token_expire_date = datetime.fromtimestamp(float(getTOKENEXPIREDATE()))
    current_time = datetime.now()
    if (current_time > token_expire_date):
        getNewAppAuthToken()
        print("Got a new auth token cause it not gud")
    return



# getSearchResult("")


#(DEBUGGING) TEST BUILD SEARCH URL THINGY
# print(buildSearchURL(BROWSE_API_BASE, {"q": {"AND":["thing1", "thing2"], "OR":["waz"]}}))


