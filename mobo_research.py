#Uses EBAY api to collect info on current & historical motherboard sales
from datetime import datetime, timedelta
import csv 
import json
import os.path
import copy
import math

import ebayAPIFuncLib

MANUFACTUER_DB = ["Gigabyte", "MSI", "Asus", "Asrock", "ProArt"]

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
    "limit": "50", #number of items to return per page (max 200, default 50)
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
    print("\nGathering item details...\n")
    modified_broad_search_results = copy.deepcopy(broad_search_results)
    for i in range(0, len(broad_search_results["itemSummaries"])):
        mobo_listing = broad_search_results["itemSummaries"][i]
        mobo_listing["brand"], mobo_listing["mpn"], mobo_listing["itemWebUrl"] = getMotherboardDetailsByItemID(mobo_listing["itemId"], log_no_mpn_api_response= True, ignore_no_mpn_exception= True)

        modified_broad_search_results["itemSummaries"][i] = mobo_listing #include added brand and MPN data into item search summary for item "i" 

        
#Among list of motherboards found, search current pricing of used/refurbished versions of that motherboard
    unique_motherboard_mpn_set = set([listing["mpn"] for listing in modified_broad_search_results["itemSummaries"]])
    motherboard_used_pricing_results_by_mpn = getUsedMotherboardPrices(unique_motherboard_mpn_set, results_limit_per_mpn = 10) 

# #Build a basic spreadsheet with the average historical sale price of each motherboard and the current going price for "for parts" motherboards 
    data = buildMotherboardSpreadsheet(modified_broad_search_results, motherboard_used_pricing_results_by_mpn)
    with open("motherboard_data" + str(datetime.date(datetime.now())) + ".csv", "w", newline='') as output_csvfile:
        writer = csv.writer(output_csvfile)
        writer.writerows(data)



def getMotherboardDetailsByItemID(item_id: str, log_no_mpn_api_response = True, ignore_no_mpn_exception = False) -> tuple[str, str]:
    '''
    Returns a tuple
        0. Brand name 
        1. MPN (manufacturer's product name) 
        2. url (direct link to listing which tends to be shorter than item summaries url)
    '''
    brand = ""
    mpn = ""
    url = ""

    response_status, response = ebayAPIFuncLib.getItemDetails(item_id, log_url=False)
    if (response_status != 200):
        raise Exception("Ebay API item details method unsuccessful\nResponse code: " + str(response_status))
    else:
        if ("brand" in response):
            brand = response["brand"]
        if ("mpn" in response):
            mpn = response["mpn"]
        elif ("localizedAspects" in response): #check localized aspects to get MPN if MPN wasn't specified 
            for aspect_dict in response["localizedAspects"]:
                if (aspect_dict["name"] == "Model"):
                    mpn = aspect_dict["value"]
                    break
        if ("itemWebUrl" in response):
            url = response["itemWebUrl"]
        
        if (mpn == "" and log_no_mpn_api_response == True):
            f = open("error_item_details_response_debug.json", 'w')
            json.dump(response, f, indent = 4)
            if (ignore_no_mpn_exception == False):
                raise Exception("MPN Not found from item details search.Copying return details to file 'error_item_details_debug_response.json'\nItemId = " + item_id)

    return brand, mpn, url



def getUsedMotherboardPrices(motherboard_mpn_set: list, results_limit_per_mpn = 20)-> dict:
    '''
    Replacement for "findUsedMotherboardHistory()"
        (atleast until Marketplace Insights API can be enabled for this project)

    Returns a dictionary where each key pertains to a unique motherboard MPN, and the value is a dictionary describing the min_price, max_price, and avg_price selling price for used/refurbished version of that motherboard currently listed on marketplace. 
    '''
    if ("" in motherboard_mpn_set):
        motherboard_mpn_set.remove("")
        #ignore the empty mpn if present

#Conduct a search for each unique motherboard based on keywords 
    used_motherboard_current_sale_pricing = {}
    for mobo_mpn in motherboard_mpn_set:
 
        #Run a search result on recent sales of the given motherboard
        motherboard_search_params = copy.deepcopy(USED_MOBO_SALES_SEARCH_PARAMS)
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


def buildMotherboardSpreadsheet(motherboard_data: dict, motherboard_used_pricing_results_by_mpn: dict) -> list[list]:
    '''
    #Parses scraped motherboard data and historical motherboard data and prepares it for csv format

    #COLUMN_LABELS = ["CHIPSET", "BRAND", "NAME", "LISTING TITLE", "LISTING TYPE", "PRICE", "CUR AVG USED PRICE", "CUR MIN USED PRICE", "CUR MAX USED PRICE", "LISTING LINK"]
    
    #Returns a list of lists, where each list is a row and inside are the values for each column
    '''
    COLUMN_LABELS = ["EST. RETURN", "EST. RETURN %" , "BRAND", "NAME", "LISTING TITLE", "LISTING TYPE", "PRICE", "CUR AVG USED PRICE", "CUR MIN USED PRICE", "CUR MAX USED PRICE", "LISTING LINK", "L_COL", "M_COL"]

    list_of_rows = [COLUMN_LABELS]
    empty_val_keyword = 0.0

    for item_row in range(0, len(motherboard_data["itemSummaries"])):
        item_listing = motherboard_data["itemSummaries"][item_row]
        new_row = [empty_val_keyword for i in range(0, len(COLUMN_LABELS))] 
        
        new_row[COLUMN_LABELS.index("BRAND")] = item_listing["brand"] if "brand" in item_listing else empty_val_keyword
        new_row[COLUMN_LABELS.index("LISTING TITLE")] = item_listing["title"] if "title" in item_listing else empty_val_keyword
        new_row[COLUMN_LABELS.index("LISTING TYPE")] = ",".join(item_listing["buyingOptions"]) if "buyingOptions" in item_listing else empty_val_keyword
        
        #pricing = direct pricing + shipping costs if any 
        direct_price = float(item_listing["price"]["value"]) if "price" in item_listing else 0.0
        shipping_price = 0 
        if ("shippingOptions" in item_listing):
            shipping_price = float(item_listing["shippingOptions"][0]["shippingCost"]["value"] if "shippingCost" in item_listing["shippingOptions"][0].keys() else 0.0)
        new_row[COLUMN_LABELS.index("PRICE")] = direct_price + shipping_price
        

        #Excel hyper link formatting 
        if ("itemWebUrl" in item_listing and len(item_listing["itemWebUrl"]) > 0):
            hyper_link = item_listing["itemWebUrl"] if "itemWebUrl" in item_listing else empty_val_keyword

            new_row[COLUMN_LABELS.index("L_COL")] = hyper_link.split("?")[0]
            #if split hyper link into two
            # new_row[COLUMN_LABELS.index("L_COL")] = hyper_link[0:math.floor(len(hyper_link)/2)]
            # new_row[COLUMN_LABELS.index("M_COL")] = hyper_link[math.floor(len(hyper_link)/2+1):len(hyper_link)]
            new_row[COLUMN_LABELS.index("LISTING LINK")] = "=HYPERLINK(" + "L" + str(item_row+2)+ "," + "\"Linkybinky\")" if "itemWebUrl" in item_listing else empty_val_keyword

        #Formatting in reference pricing details of used motherboards of this mpn type currently for sale 
        if ("mpn" in item_listing and item_listing["mpn"] != ""):
            # try:
            new_row[COLUMN_LABELS.index("NAME")] = item_listing["mpn"]
            new_row[COLUMN_LABELS.index("CUR AVG USED PRICE")] = f"{motherboard_used_pricing_results_by_mpn[item_listing['mpn']]['avg_price']:.2f}"
            new_row[COLUMN_LABELS.index("CUR MIN USED PRICE")] = motherboard_used_pricing_results_by_mpn[item_listing["mpn"]]["min_price"]
            new_row[COLUMN_LABELS.index("CUR MAX USED PRICE")] = motherboard_used_pricing_results_by_mpn[item_listing["mpn"]]["max_price"]
            # except Exception as e:
            #     print("\nLOGGING ERROR\n")
            #     print(e)
            #     print("\n" + motherboard_used_pricing_results_by_mpn)
            #     f = open("zwamn_response_debug" + ".json", 'w')
            #     json.dump(item_listing, f, indent = 4)

            
            #calculate possible return based on minimum current going price of the mobo (used)
            new_row[COLUMN_LABELS.index("EST. RETURN")] = float(new_row[COLUMN_LABELS.index("CUR MIN USED PRICE")]) - float(new_row[COLUMN_LABELS.index("PRICE")])
            new_row[COLUMN_LABELS.index("EST. RETURN %")] = (float(new_row[COLUMN_LABELS.index('EST. RETURN')]) / float(new_row[COLUMN_LABELS.index('PRICE')])) if float(new_row[COLUMN_LABELS.index("PRICE")]) != 0.0 else 0.0

        list_of_rows.append(new_row)

    return list_of_rows



compileMotherboardData()