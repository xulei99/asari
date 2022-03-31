Asari
=====
Trackable and scalable Python program for high-resolution LC-MS metabolomics data preprocessing, 

- Taking advantage of high mass resolution to prioritize mass separation and alignment
- Peak detection on a composite map instead of repeated on individual samples
- Statistics guided peak dection, based on local maxima and prominence, selective use of smoothing
- Reproducible, track and backtrack between features and EICs
- Tracking peak quality, selectiviy metrics on m/z, chromatography and annotation databases
- Performance conscious, memory and CPU uses scalable
- Fast assembly and annotation of metabolomes using chainable databases

Install
=======
- From PyPi repository: `pip3 install asari-metabolomics`. Add `--upgrade` to update to new versions.

- Or clone from source code: https://github.com/shuzhao-li/asari . One can run it as a Python module by calling Python interpreter.

Use 
===
If installed from pip, one can run `asari` as a command in a terminal, followed by a subcommand for specific tasks.

Help information is evoked without argument:

`asari`

To process all mzML files under directory mydir/projectx_dir:

`asari process --mode pos --input mydir/projectx_dir`

To get statistical description on a single file (useful to understand data and parameters):

`asari analyze --input mydir/projectx_dir/file_to_analyze.mzML`

To get annotation on a tab delimited feature table:

`asari annotate --mode pos --ppm 10 --input mydir/projectx_dir/feature_table_file.tsv`

To add automatic esitmation of min peak height, add this argument:

`--autoheight True`

Alternative to a standalone command, to run as a module via Python interpreter, one needs to point to module location, e.g.:

`python3 -m asari.main process --mode pos --input mydir/projectx_dir`

Parameters
==========
Only one parameter in asari requires attention, i.e., precision ppm is set at 5 by default. 
Most modern instruments are fine with 5 ppm, but one may want to change if needed.

For the adventurous:
Default parameters are set in `defaul_parameters.py`. 
They can be (work in progress) overwritten by user supplied parameter file in JSON.
Lastly, parameters specified in command line overwrite all the above.

Algorithms
==========
Basic data concepts follow https://github.com/shuzhao-li/metDataModel, organized as

    ├── Experiment
       ├── Sample
           ├── MassTrack
               ├── Peak
               ├── Peak
           ├── MassTrack 
               ├── Peak
               ├── Peak
        ...
       ├── Sample 
        ...
       ├── Sample 

A sample here corresponds to an injection file in LC-MS experiments. 
A MassTrack is an extracted chromatogram for a specific m/z measurement, governing full retention time.
Therefore, a MassTrack may include multiple mass traces, or EICs/XICs, as referred by literature.
Peak (an elution peak at specific m/z) is specific to a sample, but a feature is defined at the level of an experiment after correspondence.

Additional details:
- Use of MassTracks simplifies m/z correspondence
- Chromatogram construction is based on m/z values via flexible bins and frequency counts (in lieu histograms). 
- Each sample is checked for mass precision, computational calibrations recorded for mass and retention time
- Elution peak alignment is based on LOWESS 
- Use integers for RT scan numbers and intensities for computing efficiency
- Avoid mathematical curves whereas possible for computing efficiency

Selectivity is tracked for
- mSelectivity, how distinct are m/z measurements 
- cSelectivity, how distinct are chromatograhic elution peaks
- dSelectivity, how distinct are database records 

This package uses `mass2chem` and `JMS` for mass search and annotation functions.


Links
=====
Source code: https://github.com/shuzhao-li/asari

Package Repository: https://pypi.org/project/asari-metabolomics/

Related projects:

Mummichog: metabolomics pathway/network analysis

metDataModel: data models for metabolomics, used by mummichog and Azimuth DB

mass2chem: common utilities in interpreting mass spectrometry data, annotation

JMS: Json's Metabolite Services

