# 🚀 LangGraph ETL Pipeline

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-ETL-orange.svg)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Processing-yellow.svg)

## 📌 Overview
Welcome to the **LangGraph ETL Pipeline**! This project demonstrates a powerful, directed acyclic graph (DAG) based approach for Extract, Transform, and Load operations. 

**✨ New Update:** The pipeline now seamlessly ingests, cleans, and transforms a full suite of e-commerce data directly from the local `Datasets/` directory! 

## 📂 Datasets Processed
The pipeline targets three core data entities for a complete e-commerce workflow:

| Dataset | Description |
|---|---|
| 👤 **`users.csv`** | User profile data (names, emails, cities, signup dates). |
| 📦 **`products.csv`** | Product catalog including categorization and pricing. |
| 💳 **`transactions.csv`** | Purchase records linking users with the products they bought. |

## ⚙️ ETL Workflow

Using **LangGraph**, the pipeline enforces a strict DAG execution:
1. **Extract**: Validates file paths and ingests raw CSV data safely.
2. **Transform**: 
   - Normalizes columns to `snake_case`
   - Removes exact duplicates
   - Coerces dates and numerics dynamically
   - Handles nulls (via median filling and >50% drop thresholds)
   - Performs multi-step Quality Control (QC) (e.g., catching negatives, missing IDs).
3. **Load**: Dumps the beautifully pristine outputs to `data/clean/` and generates deep-dive `_metrics.json` artifacts for data observability!

## 🚀 How to Run

1. **Install Requirements:**
   ```bash
   pip install langgraph pandas pyarrow
   ```
2. **Execute the Pipeline:**
   Simply run all cells in `langgraph_etl_pipeline.ipynb` via your Jupyter Notebook environment.
3. **Check the Outputs:**
   Look inside the `data/clean/` directory for your squeaky clean processed datasets (`*_clean.csv`) and detailed runtime metrics.

## 🛠️ Requirements
- 🐍 Python 3.x
- 🐼 `pandas`
- 🕸️ `langgraph`
- 🎯 `pyarrow` *(Optional, for outputting `.parquet` files)*

---
*Built with modern data engineering practices for robust and dynamic pipeline orchestration.*
