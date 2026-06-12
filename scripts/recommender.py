import pandas as pd

funds = pd.read_csv("../data/processed/clean_fund_master.csv")
perf = pd.read_csv("../data/processed/scheme_performance_processed.csv")

recommendation_df = funds.merge(
    perf,
    on="amfi_code"
)

def recommend_funds(risk_appetite):

    return (

        recommendation_df[
            recommendation_df["risk_category"]
            .str.lower()
            ==
            risk_appetite.lower()
        ]

        .sort_values(
            "sharpe_ratio",
            ascending=False
        )

        .head(3)

    )

if __name__ == "__main__":

    print(
        recommend_funds("Moderate")
    )

for risk in recommendation_df["risk_category"].unique():

    print("\n")
    print("="*50)
    print(f"Risk Profile: {risk}")
    print("="*50)

    print(
        recommend_funds(risk)
    )