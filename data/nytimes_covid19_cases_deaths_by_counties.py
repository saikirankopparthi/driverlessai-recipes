"""Upload daily COVID-19 cases and deaths in US by counties - NY Times github
   Source:  nytimes/covid-19-data Coronavirus (Covid-19) Data in the United States
   https://github.com/nytimes/covid-19-data
"""


# Contributors: Gregory Kanevsky - gregory@h2o.ai
# Created: July 27th, 2020
# Last Updated:


from typing import Union, List, Dict
from h2oaicore.data import CustomData
import datatable as dt
import numpy as np
import pandas as pd
from h2oaicore.systemutils import user_dir
from datatable import f, g, join, by, sort, update, shift, isna


class NYTimesCovid19DailyCasesDeathsByCountiesData(CustomData):
    @staticmethod
    def create_data(X: dt.Frame = None) -> Union[
        str, List[str],
        dt.Frame, List[dt.Frame],
        np.ndarray, List[np.ndarray],
        pd.DataFrame, List[pd.DataFrame],
        Dict[str, str],  # {data set names : paths}
        Dict[str, dt.Frame],  # {data set names : dt frames}
        Dict[str, np.ndarray],  # {data set names : np arrays}
        Dict[str, pd.DataFrame],  # {data set names : pd frames}
    ]:
        # define date column and forecast horizon
        date_col = 'date'
        group_by_cols = ["state", "county"]
        forecast_len = 7

        # get COVID19 data from NYTimes github
        us_counties = dt.fread("https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv",
                               columns={"fips": dt.str32})

        # get counties population
        # https://www2.census.gov/programs-surveys/popest/datasets/2010-2019/counties/totals/
        counties_pop = dt.fread(
            "https://www2.census.gov/programs-surveys/popest/datasets/2010-2019/counties/totals/co-est2019-alldata.csv")
        counties_pd = counties_pop[:, ["STATE", "COUNTY", "POPESTIMATE2019"]].to_pandas()
        counties_pd = counties_pd.apply(lambda x: ["{:02d}".format(x[0]) + "{:03d}".format(x[1]), x.POPESTIMATE2019],
                                        axis=1, result_type='expand')
        counties_pd.rename(columns={0: 'fips', 1: 'pop'}, inplace=True)
        counties_pop = dt.Frame(counties_pd)
        counties_pop.key = "fips"

        # augment data with county population figures and create adjusted case and death counts
        series_cols = ["cases", "deaths"]
        aggs = {f"{col}100k": dt.f[col] / (dt.g.pop / 100000) for col in series_cols}
        us_counties[:, update(pop = g.pop, pop100k = g.pop / 10000, **aggs), join(counties_pop)]

        # remove rows without fips defined (resulted in unmatched rows after left outer join)
        del us_counties[isna(f.pop), :]

        # produce lag of 1 unit and add as new feature for each shift column
        series_cols.extend([col + "100k" for col in series_cols])
        aggs = {f"{col}_yesterday": shift(f[col]) for col in series_cols}
        us_counties[:, update(**aggs), sort(date_col), by(group_by_cols)]

        # update NA lags to 0
        aggs = {f"{col}_yesterday": 0 for col in series_cols}
        us_counties[isna(f[f"{series_cols[0]}_yesterday"]), update(**aggs)]

        # compute daily values by differentiating
        aggs = {f"{col}_daily": f[col] - f[f"{col}_yesterday"] for col in series_cols}
        us_counties[:, update(**aggs), sort(date_col), by(group_by_cols)]

        # delete columns with yesterday (shift) values
        series_cols_to_delete = [f"{col}_yesterday" for col in series_cols]
        del us_counties[:, series_cols_to_delete]

        # set negative daily values to 0
        us_counties[f.cases_daily < 0, [f.cases_daily, f.cases100k_daily]] = 0
        us_counties[f.deaths_daily < 0, [f.deaths_daily, f.deaths100k_daily]] = 0

        # determine threshold to split train and test based on forecast horizon
        dates = dt.unique(us_counties[:, date_col])
        split_date = dates[-(forecast_len + 1):, :, dt.sort(date_col)][0, 0]
        test_date = dates[-1, :, dt.sort(date_col)][0, 0]

        # split data to honor forecast horizon in test set
        df = us_counties[date_col].to_pandas()
        train = us_counties[df[date_col] <= split_date, :]
        test = us_counties[df[date_col] > split_date, :]

        # return [train, test] and rename dataset names as needed
        return {f"covid19_daily_{split_date}_by_counties_train": train,
                f"covid19_daily_{test_date}_by_counties_test": test}
