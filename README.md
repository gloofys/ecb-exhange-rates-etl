# ECB Exchange Rates ETL

This project implements a simple ETL (Extract–Transform–Load) pipeline that downloads Euro foreign exchange reference rates from the European Central Bank (ECB), processes the data, and writes the results into a Markdown table.

The program extracts daily and historical exchange rates, selects specific currencies, calculates historical averages, and saves the result into a file in the project root.

---

## ETL Process

### Extract

Exchange rate data is downloaded from the ECB:

Daily rates:
https://www.ecb.europa.eu/stats/eurofxref/eurofxref.zip

Historical rates:
https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip

---

### Transform

The program:

- Loads daily and historical exchange rates
- Selects only the following currencies:
  - USD
  - SEK
  - GBP
  - JPY
- Calculates the historical mean exchange rate for each selected currency

---

### Load

The program generates a Markdown table with the following columns:

Currency Code | Rate | Mean Historical Rate

The result is saved to:

exchange_rates.md

in the project root folder.

---

## Requirements

- Python 3.12 or newer

---

## Installation

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment.

### Windows

```bash
.venv\Scripts\activate
```

### Linux / Mac

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Program

Run the program from the project root folder:

```bash
python -m src.main
```

After running the program, the file

```
exchange_rates.md
```

will be created in the project root folder.