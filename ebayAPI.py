import json

def _loadKeyDict(file_location: str) -> dict:
    key_file = open(file_location, "r")
    json_dict = json.load(key_file)
    key_file.close()
    return json_dict

def getAUTHTOKEN() -> str:
    '''
    Get api token from .json key storage
    Auth token used to make Ebay api requests
    '''
    return _loadKeyDict("api_keys.json")["AUTH_TOKEN"]

def getTOKENEXPIREDATE() -> str:
    '''
    Get api token exprie date from .json key storage
    '''
    keys_dict = _loadKeyDict("api_keys.json")
    return keys_dict["TOKEN_EXPIRE_DATE"] if keys_dict["TOKEN_EXPIRE_DATE"] != "" else 0

def getCONTEXTLOCATION() -> str:
    '''
    Get get context location from .json key storage
    Context location used in headers to improve accuracy of Ebay api requests
    '''    
    return _loadKeyDict("api_keys.json")["CONTEXT_LOCATION"]

def getCLIENTID() -> str:
    '''
    Get client ID from .json key storage
    Client ID combined with client secret to acquire a new application authentication token
    '''    
    return _loadKeyDict("api_keys.json")["CLIENT_ID"]

def getCLIENTSECRET() -> str:
    '''
    Get get client secret .json key storage
    Client secret combined with client ID to acquire a new applicaiton authentication token 
    '''    
    return _loadKeyDict("api_keys.json")["CLIENT_SECRET"]

def setAUTHTOKEN(token_str: str):
    keys_dict = _loadKeyDict("api_keys.json")
    keys_dict["AUTH_TOKEN"] = token_str
    keys_file = open("api_keys.json", "w")
    json.dump(keys_dict, keys_file, indent=4)

def setTOKENEXPIREDATE(token_expire_time: str):
    keys_dict = _loadKeyDict("api_keys.json")
    keys_dict["TOKEN_EXPIRE_DATE"] = token_expire_time
    keys_file = open("api_keys.json", "w")
    json.dump(keys_dict, keys_file, indent=4)


