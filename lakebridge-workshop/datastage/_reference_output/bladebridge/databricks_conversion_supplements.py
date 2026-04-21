# this file contains functions supporting various operations encountered on Databricks conversion projects
from pyspark.sql import SparkSession
from pyspark.sql import DataFrame


class DatabricksConversionSupplements:
    @staticmethod
    def conform_df_columns(df: DataFrame, new_col_names: list) -> DataFrame:
        if 'sys_row_id' in df.columns and not 'sys_row_id' in new_col_names:
            new_col_names.append('sys_row_id')

        if 'source_record_id' in df.columns and not 'source_record_id' in new_col_names:
            new_col_names.append('source_record_id')

        if len(new_col_names) != len(df.columns):
            raise ValueError("New column names list must match the number of columns in the DataFrame.")

        return df.withColumnsRenamed(dict(zip(df.columns, new_col_names)))

    @staticmethod
    def conform_df_columns_dtypes(df: DataFrame, new_col_dtypes: list) -> DataFrame:
        if len(df.columns) != len(new_col_dtypes):
            raise ValueError("New column dtypes list must match the number of columns in the DataFrame")

        return df.withColumns(dict(zip(df.columns, new_col_dtypes)))
