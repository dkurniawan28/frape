### Store Partnership

Manajemen tipe store dan PKS partner

📖 Dokumentasi lengkap flow bisnis (POS per store, piutang fee bulanan, order material,
ongkir) dan API (`create_store_sales_order`, `create_pos_sale`): [docs/flows_and_api.md](docs/flows_and_api.md)
(versi halaman visual: [docs/flows_and_api.html](docs/flows_and_api.html))

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app store_partnership
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/store_partnership
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
