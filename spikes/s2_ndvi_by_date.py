import sys, numpy as np, pystac_client, planetary_computer as pc
from odc.stac import load
BBOX=[74.9,29.45,75.15,29.6]  # ~25x17 km around Sirsa town
cat=pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",modifier=pc.sign_inplace)
for win in ["2025-10-14/2025-10-31","2026-10-14/2026-10-31"]:
    items=list(cat.search(collections=["sentinel-2-l2a"],bbox=BBOX,datetime=win,query={"eo:cloud_cover":{"lt":30}}).items())
    for it in sorted(items,key=lambda i:i.datetime):
        print(it.datetime.date(), it.properties.get("s2:mgrs_tile"), "pb",it.properties.get("s2:processing_baseline"), "cc",round(it.properties["eo:cloud_cover"],1))
    ds=load(items,bands=["B04","B08","SCL"],bbox=BBOX,resolution=20,crs="EPSG:32643",groupby="solar_day").compute()
    for t in range(ds.sizes["time"]):
        s=ds.isel(time=t); scl=s.SCL.values; ok=np.isin(scl,[4,5])
        r=s.B04.values.astype(float)-1000; n=s.B08.values.astype(float)-1000
        v=np.where(ok,(n-r)/(n+r+1e-9),np.nan)
        print("  ",str(s.time.values)[:10],"valid",round(ok.mean(),2),"nodata0",round((s.B04.values==0).mean(),2),
              "NDVI p25/50/75",np.round(np.nanpercentile(v,[25,50,75]),2),"frac>0.5",round(np.nanmean(v>0.5),2),"frac<0.25",round(np.nanmean(v<0.25),2))
