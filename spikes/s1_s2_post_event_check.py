import numpy as np, pystac_client, planetary_computer as pc
from odc.stac import load
BBOX=[74.9,29.45,75.15,29.6]
cat=pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",modifier=pc.sign_inplace)
items=list(cat.search(collections=["sentinel-2-l2a"],bbox=BBOX,datetime="2026-10-29/2026-10-31").items())
print("S2 post items",[(i.id[11:19],i.properties['s2:mgrs_tile'],round(i.properties['eo:cloud_cover'],1)) for i in items])
if items:
    ds=load(items,bands=["B04","B08","SCL"],bbox=BBOX,resolution=20,crs="EPSG:32643",groupby="solar_day").compute()
    for t in range(ds.sizes["time"]):
        s=ds.isel(time=t); ok=np.isin(s.SCL.values,[4,5]); r=s.B04.values-1000.; n=s.B08.values-1000.
        v=np.where(ok,(n-r)/(n+r+1e-9),np.nan)
        print(str(s.time.values)[:10],"valid",round(ok.mean(),2),"B08 p50",np.nanpercentile(s.B08.values,50),"NDVI p25/50/75",np.round(np.nanpercentile(v,[25,50,75]),2),"frac<0.25",round(np.nanmean(v<0.25),2))
s1=list(cat.search(collections=["sentinel-1-rtc"],bbox=BBOX,datetime="2026-10-08/2026-10-31").items())
print("S1 items",[(i.datetime.isoformat()[:16],i.properties.get('sat:orbit_state')) for i in s1])
ds=load(s1,bands=["vv","vh"],bbox=BBOX,resolution=20,crs="EPSG:32643",groupby="solar_day").compute()
for t in range(ds.sizes["time"]):
    s=ds.isel(time=t); vv=10*np.log10(np.clip(s.vv.values,1e-6,None)); vh=10*np.log10(np.clip(s.vh.values,1e-6,None))
    print(str(s.time.values)[:10],"VV dB p50",round(np.nanmedian(vv),2),"VH dB p50",round(np.nanmedian(vh),2),"nan frac",round(np.isnan(s.vv.values).mean(),2), "frac VV<-18 (water-like)",round(np.nanmean(vv<-18),3))
