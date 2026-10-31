import numpy as np, pystac_client, planetary_computer as pc
from odc.stac import load
BBOX=[74.9,29.45,75.15,29.6]
cat=pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",modifier=pc.sign_inplace)
items=list(cat.search(collections=["sentinel-2-l2a"],bbox=BBOX,datetime="2026-10-18/2026-10-31",query={"eo:cloud_cover":{"lt":5}}).items())
for it in items: print(it.id, it.assets["B08"].href.split("?")[0][-60:])
ds=load(items,bands=["B02","B03","B04","B08","B11","SCL"],bbox=BBOX,resolution=20,crs="EPSG:32643",groupby="solar_day").compute()
for t in range(ds.sizes["time"]):
    s=ds.isel(time=t); print(str(s.time.values)[:10])
    for b in ["B02","B03","B04","B08","B11"]:
        v=s[b].values.astype(float); print("  ",b,"p10/50/90",np.percentile(v,[10,50,90]).round(0))
    print("   SCL classes",dict(zip(*np.unique(s.SCL.values,return_counts=True))))
    print("   corr(B04,B08)",round(np.corrcoef(s.B04.values.ravel(),s.B08.values.ravel())[0,1],3))
