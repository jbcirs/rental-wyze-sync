import azure.functions as func
import json
    
bp01 = func.Blueprint()
@bp01.route(route="route01")
def method01(req:func.HttpRequest) -> func.HttpRequest:
    return func.HttpResponse (
        json.dumps({
        'version': 1
        })
    )