# -*- coding: utf-8 -*-
"""
Created on Wed Dec 11 09:06:45 2024

@author: armen
"""

import pandas as pd
import geopandas as gpd
import numpy as np

# Load datasets
economic_data = pd.read_csv('../../Datasets/econ_crop_data/final_crop_economic_data.csv',index_col=0)
meta_landiq20 = gpd.read_file(r"C:\Users\armen\Documents\ArcGIS\Projects\COEQWAL\COEQWAL.gdb", layer='landiq20_CVID_GW_DU_SR')
crop_mapping = pd.read_excel("../../Datasets/econ_crop_data/bridge openag.xlsx", sheet_name='landiq20 & openag')
landiq20_columns = meta_landiq20.columns
# 'GSA_ID','DU_ID','Subregion','COUNTY','HYDRO_RGN'
#%%
landiq20 = meta_landiq20.copy()
# Selected column for grouping
grouping_column = 'DU_ID'
# Create crop mapping dictionary
openag_mapping_dict = crop_mapping.set_index('CROPTYP2')['Crop_OpenAg'].to_dict()
landiq20['Crop_OpenAg'] = landiq20['CROPTYP2'].map(openag_mapping_dict)


landiq20 = landiq20.merge(economic_data, left_on=['COUNTY', 'Crop_OpenAg'], right_on=['County', 'Crop_OpenAg'], how='left')
landiq20_head = landiq20.head()
landiq20 = landiq20[['COUNTY', 'Crop_OpenAg', 'Crop_Subtype', 'ACRES', 'GSA_Name', grouping_column, 
                             'price_2020', 'yield_2020','Acres_2020','fraction']]
#%%
landiq20_crop_area = landiq20.groupby([grouping_column, 'Crop_OpenAg'])['ACRES'].sum().reset_index()
# Group and calculate weighted values
def calculate_weighted_values(group):
    # acres_sum = group['ACRES'].sum()
    return pd.Series({
        'Price': (group['price_2020'] * group['ACRES']).sum() / group['ACRES'].sum(),
        'Yield': (group['yield_2020'] * group['ACRES']).sum() / group['ACRES'].sum(),
        'Fraction': (group['fraction'] * group['ACRES']).sum() / group['ACRES'].sum(),
        'County_Acres': group['Acres_2020'].iloc[0] if not group['Acres_2020'].isna().all() else np.nan,
    })
landiq20_econ = landiq20.groupby([grouping_column, 'Crop_OpenAg', 'Crop_Subtype']).apply(calculate_weighted_values).reset_index()

landiq20_grouped = pd.merge(landiq20_crop_area, landiq20_econ, how='left', on = ['DU_ID', 'Crop_OpenAg'])
landiq20_grouped = landiq20_grouped[
    (landiq20_grouped[grouping_column].str.strip() != '') &  # Remove rows where 'DU_ID' is empty
    (landiq20_grouped['Crop_Subtype'] != 'Idle') &   # Remove rows where 'Crop_OpenAg' is 'Idle'
    (landiq20_grouped['Crop_Subtype'] != 'na')              # Remove rows where 'DU_ID' is Na
]

##this is to confirm that fractions are correct (sum of fractions should be equal to the number of crops)
pivot_table = landiq20_grouped.pivot_table(index='DU_ID', columns='Crop_Subtype', values='Fraction', aggfunc='first')
grapes_tomatoes_columns = [col for col in pivot_table.columns if 'Grapes' in col or 'Tomatoes' in col]
pivot_table = pivot_table[grapes_tomatoes_columns]
pivot_table['row_sum'] = pivot_table.sum(axis=1)

#%%
def calculate_weighted_values(group):
    # acres_sum = group['ACRES'].sum()
    return pd.Series({
        'Price': (group['Price'] * group['Fraction']).sum(),
        'Yield': (group['Yield'] * group['Fraction']).sum(),
    })

landiq20_grouped_new = landiq20_grouped.groupby([grouping_column, 'Crop_OpenAg','ACRES'], group_keys=False).apply(calculate_weighted_values, include_groups=False).reset_index()

#%%
final_data = landiq20_grouped_new.copy()
# Adjust column names and assign final prices and yields for 'Pasture'
final_data = final_data[[grouping_column, 'Crop_OpenAg', 'Price', 'Yield', 'ACRES']]
final_data.columns = [grouping_column, 'Crop_OpenAg', 'final_price', 'final_yield', 'Total_Acres']
final_data.loc[final_data['Crop_OpenAg'] == 'Pasture', ['final_price', 'final_yield']] = [215, 3.5]

# Categorize crops as Perennial or Non-Perennial
final_data['Crop_Type'] = np.where(
    final_data['Crop_OpenAg'].isin(['Almonds', 'Grapes Wine', 'Grapes Table', 'Orchards', 'Pistachios', 'Subtropical', 'Walnuts', 'Young Perennial']),
    'Perennial',
    'Non-Perennial')

# Split the data into perennial and non-perennial
perennial_data = final_data[final_data['Crop_Type'] == 'Perennial']
non_perennial_data = final_data[final_data['Crop_Type'] == 'Non-Perennial']

# Calculate young perennial area and merge it
young_perennial_area = perennial_data[perennial_data['Crop_OpenAg'] == 'Young Perennial'][[grouping_column, 'Total_Acres']]
non_young_perennial = perennial_data[perennial_data['Crop_OpenAg'] != 'Young Perennial']
non_young_perennial['Crop_Percentage'] = non_young_perennial.groupby(grouping_column)['Total_Acres'].transform(lambda x: (x / x.sum()) * 100)
perennial_data = pd.merge(perennial_data, non_young_perennial[[grouping_column, 'Crop_OpenAg', 'Crop_Percentage']], on=[grouping_column, 'Crop_OpenAg'])
perennial_data = pd.merge(perennial_data, young_perennial_area, on=grouping_column, how='left')

# Fill NaN values for young perennial area and calculate area adjustments
perennial_data['Total_Acres_y'] = perennial_data['Total_Acres_y'].fillna(0)
perennial_data['Area_Adjustment'] = (perennial_data['Crop_Percentage'] / 100) * perennial_data['Total_Acres_y']

# Adjust acres and finalize the dataset
perennial_data['Adjusted_Acres'] = perennial_data['Total_Acres_x'] + perennial_data['Area_Adjustment']
perennial_data = perennial_data[[grouping_column, 'Crop_OpenAg', 'final_price', 'final_yield', 'Adjusted_Acres', 'Crop_Type']]
perennial_data.columns = [grouping_column, 'Crop_OpenAg', 'final_price', 'final_yield', 'Total_Acres', 'Crop_Type']

# Combine perennial and non-perennial data
final_aggregated_data = pd.concat([perennial_data, non_perennial_data])
final_aggregated_data = final_aggregated_data[[grouping_column, 'Crop_OpenAg', 'final_price', 'final_yield', 'Total_Acres']]
final_aggregated_data.columns = [grouping_column, 'Crop', 'Price ($/unit)', 'Yield (unit/acre)', 'Area (acre)']
final_aggregated_data.to_csv('../../Datasets/econ_crop_data/final_final_crop_economic_data.csv')