import numpy as np, pystac_client, planetary_computer as pc
from odc.stac import load
BBOX=[75.35,29.45,75.6,29.6]  # Fatehabad
cat=pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",modifier=pc.sign_inplace)
items=list(cat.search(collections=["sentinel-2-l2a"],bbox=BBOX,datetime="2026-10-15/2026-10-31").items())
print([(i.id[11:19],i.properties['s2:mgrs_tile'],round(i.properties['eo:cloud_cover'],1)) for i in sorted(items,key=lambda i:i.datetime)])
ds=load(items,bands=["B04","B08","SCL"],bbox=BBOX,resolution=20,crs="EPSG:32643",groupby="solar_day").compute()
for t in range(ds.sizes["time"]):
    s=ds.isel(time=t); ok=np.isin(s.SCL.values,[4,5]); r=s.B04.values-1000.; n=s.B08.values-1000.
    v=np.where(ok&~np.isnan(n),(n-r)/(n+r+1e-9),np.nan)
    print(str(s.time.values)[:10],"valid",round(ok.mean(),2),"B08 nan",round(np.isnan(s.B08.values).mean(),2),"NDVI p50",np.round(np.nanmedian(v),2) if np.any(~np.isnan(v)) else None,"frac<0.25",round(np.nanmean(v<0.25),2) if np.any(~np.isnan(v)) else None)
