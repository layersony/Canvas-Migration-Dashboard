import requests, time

def paginate(url, headers):
    results = []
    while url:
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()

            if res.status_code != 200:
                print(res.error)
                break

            results.extend(res.json())
            url = res.links.get("next", {}).get("url")
            time.sleep(0.1)  # avoid rate limit
        except requests.exceptions.HTTPError as http_err:
            print('1')
            return {
                "error": f"HTTP error: {http_err}",
                "status_code": res.status_code if 'res' in locals() else 500,
            }
        except requests.exceptions.ConnectionError as conn_err:
            return {
                "error": f"Connection failed: {conn_err}",
                "status_code": 503
            }

        except requests.exceptions.Timeout as timeout_err:
            return {
                "error": f"Request timed out: {timeout_err}",
                "status_code": 504
            }
        
        except requests.exceptions.RequestException as err:
            return {
                "error": f"Unexpected error: {err}",
                "status_code": 500
            }
        
    return results

def post(url, headers, data):
    r = requests.post(url, headers=headers, data=data)
    if not r.ok:
        print(f"POST failed: {r.status_code} {r.text}")
    return r.json()

def put(url, headers, data):
    r = requests.put(url, headers=headers, data=data)
    if not r.ok:
        print(f"PUT failed: {r.status_code} {r.text}")
    return r
