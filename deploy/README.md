# Build image dari repo ini

`apps.json` di folder ini dipakai bareng [`frappe_docker`](https://github.com/frappe/frappe_docker)
(repo resmi Frappe, bukan bagian dari repo ini) untuk build image ERPNext yang sudah
include app `store_partnership` langsung dari GitHub — tidak perlu `docker cp` atau
`docker commit` manual.

## Cara pakai

```bash
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
cp /path/to/store_partnership/deploy/apps.json apps.json

docker build \
 --no-cache \
 --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
 --build-arg=FRAPPE_BRANCH=version-16 \
 --secret=id=apps_json,src=apps.json \
 --tag=store_partnership_custom:16 \
 --file=images/layered/Containerfile .
```

Image hasilnya (`store_partnership_custom:16`) berisi `frappe` + `erpnext` +
`store_partnership`, siap dipakai di `docker-compose` (isi `CUSTOM_IMAGE`/`CUSTOM_TAG`
di `.env` sesuai tag di atas). Detail lengkap ada di dokumentasi resmi
[Build Setup frappe_docker](https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md).

## Data

Image ini cuma berisi kode — data (Store, PKS Agreement, transaksi, dll) tidak ikut
ter-bake dan harus di-restore terpisah lewat `bench restore` dari backup site
(`bench --site <site> backup --with-files`). Ini standar arsitektur Frappe: image =
kode, backup = data, digabung saat deploy.
