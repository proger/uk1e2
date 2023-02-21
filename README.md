# uk1e2

Major sources:

- uk1e2.csv by Saturday Team (awaiting copy permission)
- youtube.ids by Natalia
- news by Mykola (todo: copyright statement)

## Setup

This Python project uses [hatch](https://hatch.pypa.io/latest/intro/) to manage the uk1e2 package.

Please install the package using the following command.

```
pip install hatch
pip install -e .
```
To create a virtual environment, you may use `hatch shell`.



## Changelog

- created the `prep_test_data.py` local test set preparation tool 
It allows for source file downloading (and audio extraction) and preparing scp and text files
- absense of `https://a.wilab.org.ua/uk1e2/mp4/6_5.mp4` is detected while source downloading
