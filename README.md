# CMSIS-SVD file parser
A script to extract peripheral information from CMSIS-SVD file, more info about this [here](https://www.keil.com/pack/doc/CMSIS/SVD/html/svd_Format_pg.html)

## Dependencies
- This script requires [xmltodict](https://github.com/martinblech/xmltodict), after donwloading, put it beside this script.
- Python 3.8.x

## How to use
`python svd_parser.py "path to .svd file" PERI_NAME` \
Example: `python svd_parser.py "stmf103c8.svd" SPI1`
