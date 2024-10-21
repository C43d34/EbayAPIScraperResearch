#Uses EBAY api to collect info on current & historical motherboard sales
from datetime import datetime, timedelta
import csv 
import json
import os.path

import ebayAPIFuncLib

MANUFACTUER_DB = ["Gigabyte", "MSI", "Asus", "Asrock"]

GENERIC_MOBO_SEARCH_PARAMS = {
    "q": { #keyswords concatenated into a string => 
        "AND": ["Motherboard"], #"k1 k2" space separated means k1 AND k2
        "OR": ["Z690", "Z790", "B660", "B760", "X670", "X670E", "X870", "X870E"] #"(k1, k2, ...)" comma separated means k1 OR k2 or ... 
                    #could possibly get fancy with OR and AND by having OR be conditionally placed between AND search parameters so we can search for (X or Y) and (A or B)
                    # => "(x, y) (a, b)" is how it would look in url I think
                    #current structing of URL with OR params will just be passed all at once so this conceptual functionality isn't possibly yet. 
        },              
    "filter": { #different filters with each their own formatting => {filter1: params}, {filter2: params}
        "conditionIds": "{7000}", #for parts condition 
        # "itemEndDate": "[..2018-12-14T07:47:48Z]", #item listing end from now till 24 hours 
        "buyingOptions" : "{FIXED_PRICE|AUCTION}",
        }, 
            
    # "sort": "", #sort=price from lowest to highest price (maybe behave strangely with bidding items which I need to look)
    "limit": "20", #number of items to return per page (max 200, default 50)
    # "offset": "0" #specifies number of items to skip in result set (control pagination of the output) 
}

USED_MOBO_SALES_SEARCH_PARAMS = {
        "q": { #keyswords concatenated into a string => 
        "AND": ["Motherboard"], #"k1 k2" space separated means k1 AND k2
        "OR": [] #"(k1, k2, ...)" comma separated means k1 OR k2 or ... 
                    #could possibly get fancy with OR and AND by having OR be conditionally placed between AND search parameters so we can search for (X or Y) and (A or B)
                    # => "(x, y) (a, b)" is how it would look in url I think
                    #current structing of URL with OR params will just be passed all at once so this conceptual functionality isn't possibly yet. 
        },              
    "filter": { #different filters with each their own formatting => {filter1: params}, {filter2: params}
        "conditions": "{USED}", #for parts condition 
        "conditionIds": "{2000|2500|3000}" #2000 (certified refurbished), 2500 (seller refurbished), 3000 (used)
        # "itemEndDate": "[..2018-12-14T07:47:48Z]", #item listing end from now till 24 hours 
        }, 
            
    # "sort": "", #sort=price from lowest to highest price (maybe behave strangely with bidding items which I need to look)
    "limit": "5", #number of items to return per page (max 200, default 50)
    # "offset": "0" #specifies number of items to skip in result set (control pagination of the output) 
}

def compileMotherboardData():
#Search a generic list of motherboards for sale 
    #Z690, Z790, AMD motherboards..... LGA Sockets only
    #Filter for "for parts" condition

    # GENERIC_MOBO_SEARCH_PARAMS["filter"]["itemEndDate"] = "[.." + (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ") + "]"
    response_status, broad_search_results = ebayAPIFuncLib.getSearchResults(GENERIC_MOBO_SEARCH_PARAMS, log_url= True)
    if (response_status != 200):
        raise Exception("Ebay API browse method unsuccessful\nResponse code: " + str(response_status))


    #(TODO) Filter for anything (auctions) that expires within 24 hours from now (newer auctions tend to have lower and therefore less relevant prices)


# (DEPRECATED) #Among list of motherboards found, search with historical data on used (not for parts) motherboards. 
    #Time range should be 6 months or so...
    # motherboard_used_history_search_results = findUsedMotherboardHistory(broad_search_results.keys())
    
#Formally define the Brand and MPN for each motherboard
    modified_broad_search_results = broad_search_results
    for i in range(0, len(broad_search_results["itemSummaries"])):
        mobo_listing = broad_search_results["itemSummaries"][i]
        mobo_listing["brand"], mobo_listing["mpn"] = getMotherboardBrandAndMPNByItemID(mobo_listing["itemId"])

        modified_broad_search_results["itemSummaries"][i] = mobo_listing #include added brand and MPN data into item search summary for item "i" 

#Among list of motherboards found, search current pricing of used/refurbished versions of that motherboard
    unique_motherboard_mpn_set = set([listing["mpn"] for listing in modified_broad_search_results["itemSummaries"]])
    motherboard_used_pricing_results_by_mpn = getUsedMotherboardPrices(unique_motherboard_mpn_set) 

# #Build a basic spreadsheet with the average historical sale price of each motherboard and the current going price for "for parts" motherboards 
    data = buildMotherboardSpreadsheet(modified_broad_search_results, motherboard_used_pricing_results_by_mpn)
    with open("motherboard_data" + str(datetime.date(datetime.now())) + ".csv", "w", newline='') as output_csvfile:
        writer = csv.writer(output_csvfile)
        writer.writerows(data)



def getMotherboardBrandAndMPNByItemID(item_id: str) -> tuple[str, str]:
    '''
    Returns a tuple
        0. Brand name 
        1. MPN (manufacturer's product name) 
    '''
    brand = ""
    mpn = ""

    response_status, response = ebayAPIFuncLib.getItemDetails(item_id)
    if (response_status != 200):
        raise Exception("Ebay API browse method unsuccessful\nResponse code: " + str(response_status))
        
    brand = response["brand"]
    mpn = response["mpn"]
    return brand, mpn



def getUsedMotherboardPrices(motherboard_mpn_set: list, results_limit_per_mpn = 20)-> dict:
    '''
    Replacement for "findUsedMotherboardHistory()"
        (atleast until Marketplace Insights API can be enabled for this project)

    Returns a dictionary where each key pertains to a unique motherboard MPN, and the value is the average selling price for used/refurbished version of that motherboard. 
    '''
#Conduct a search for each unique motherboard based on keywords 
    used_motherboard_current_sale_pricing = {}
    for mobo_mpn in motherboard_mpn_set:

        #Run a search result on recent sales of the given motherboard
        motherboard_search_params = USED_MOBO_SALES_SEARCH_PARAMS.copy()
        motherboard_search_params["q"]["AND"].append(mobo_mpn)
        motherboard_search_params["limit"] = results_limit_per_mpn
        
        response_status, search_results = ebayAPIFuncLib.getSearchResults(motherboard_search_params, log_url= True)
        if (response_status != 200):
            raise Exception("Ebay API browse method unsuccessful\nResponse code: " + str(response_status))
            return

        #Calculate relevant pricing from recent sales         
        min_price, max_price, avg_price = ebayAPIFuncLib.util_CompileSalePriceStatsOfSearchResults(search_results["itemSummaries"])

        #Categorize the following motherboard historical pricing data 
        used_motherboard_current_sale_pricing[mobo_mpn] = {"min_price": min_price,
                                                            "max_price": max_price,
                                                            "avg_price": avg_price} 

    return used_motherboard_current_sale_pricing 


 
def findUsedMotherboardHistory(motherboard_mpn_set: list, months_to_search = 6)-> dict:
    '''
    (DEPRECATED)
        - Deprecated because can't use item_sales (Marketplace Insights) API without special allowances from EBay
        Therefore, it's impossible to use api to make historical search until further notice.
        - For replacement, see "getUsedMotherboardPrices()" 

    Each key is paired with a value representing the average historical sale of that motherboard in the used market.

    Returns a dictionary where each key pertains to a unique motherboard, and the value is the average historical sold price of that motherboard within the time frame. 
    '''
#Conduct a historical search for each unique motherboard based on keywords 
    used_motherboard_historical_sale_pricing = {}
    for mobo_mpn in motherboard_mpn_set:
        #Run a search result on recent sales of the given motherboard
        response_status, historical_search_results = ebayAPIFuncLib.getSearchResults(USED_MOBO_SALES_SEARCH_PARAMS, log_url= True)
        if (response_status != 200):
            raise Exception("Ebay API browse method unsuccessful\nResponse code: " + str(response_status))
            return

        #Calculate relevant pricing from recent sales         
        min_price, max_price, avg_price = ebayAPIFuncLib.util_CompileSalePriceStatsOfSearchResults(historical_search_results["itemSummaries"])

        #Categorize the following motherboard historical pricing data 
        used_motherboard_historical_sale_pricing[mobo_mpn] = {"min_price": min_price,
                                                              "max_price": max_price,
                                                              "avg_price": avg_price} 

    return used_motherboard_historical_sale_pricing 


def buildMotherboardSpreadsheet(motherboard_data: dict, historical_used_motherboard_sales_data: dict) -> list[list]:
    '''
    #Parses scraped motherboard data and historical motherboard data and prepares it for csv format
    '''

    return [[1, "a"], [2, "b"], [3, "c"]]



compileMotherboardData()