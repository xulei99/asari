'''
Classes of MassGrid and CompositeMap.
'''
import pandas as pd
from mass2chem.search import *

from .mass_functions import *
from .chromatograms import *
from .peaks import *
from .samples import SimpleSample


class MassGrid:
    '''
    MassGrid is the concept for m/z correspondence in asari.
    This shares similarity to FeatureMap in OpenMS, but the correspondence 
    in asari takes adavantage of high m/z resolution first before feature detection.
    '''
    def __init__(self, cmap=None, experiment=None):
        '''
        Initiating MassGrid by linking to CompositeMap and ext_Experiment instances.

        Parameters
        ----------
        cmap : CompositeMap instance.
        experiment : ext_Experiment instance.
        '''
        self.experiment = experiment
        self.CMAP = cmap
        self.reference_sample_instance = self.CMAP.reference_sample_instance
        self.max_ref_rtime = self.CMAP.max_ref_rtime
        self.list_sample_names = self.CMAP.list_sample_names
        self._number_of_samples_ = self.CMAP._number_of_samples_
        
    def build_grid_sample_wise(self):
        '''
        Align one sample a time to reference m/z grid, based on their anchor m/z tracks.
        One of the two methods to build the grid.
        This is better for reliable assembly of small number of samples.

        See also
        --------
        build_grid_by_centroiding
        '''
        self._initiate_mass_grid()
        sample_ids = self.experiment.valid_sample_ids
        sample_ids.pop(self.experiment.reference_sample_id)
        for sid in sample_ids:
            SM = SimpleSample(self.experiment.sample_registry[sid],
                experiment=self.experiment, database_mode=self.experiment.database_mode, 
                mode=self.experiment.mode)
            self.add_sample(SM)

    def build_grid_by_centroiding(self):
        '''
        Assemble mass grid by grouping m/z values to centroids.
        Each centroid can have no more than one mass track per sample.
        One of the two methods to build the grid.
        This is more efficient for large number of samples.

        See also
        --------
        build_grid_sample_wise
        '''
        all = []
        for ii in range(self._number_of_samples_):
            sid = self.experiment.valid_sample_ids[ii]
            for jj in self.experiment.sample_registry[sid]['track_mzs']:
                all.append(
                    (jj[0], jj[1], ii)      # m/z, masstrack_id, sample_index
                )
        all.sort()

        all_bins = self.bin_track_mzs(all, self.experiment.reference_sample_id)

        self.MassGrid = pd.DataFrame(
            np.full((len(all_bins), self._number_of_samples_), None),
            columns=self.CMAP.list_sample_names,
        )
        for jj in range(len(all_bins)):
            for (mz, track_id, sample_ii) in all_bins[jj][1]:
                self.MassGrid.iloc[jj, sample_ii] = track_id
        
        mz_list = [x[0] for x in all_bins]
        self.MassGrid.insert(0, "mz", mz_list)          # add extra col for mz

        # determine anchor and landmark mass tracks
        list_mass_tracks = []
        for ii in range(len(mz_list)):
            list_mass_tracks.append({'id_number': ii, 'mz': mz_list[ii],})
        self.anchor_mz_pairs = find_mzdiff_pairs_from_masstracks(
            list_mass_tracks, mz_tolerance_ppm=self.experiment.parameters['mz_tolerance_ppm']
            )
        self._mz_landmarks_ = flatten_tuplelist(self.anchor_mz_pairs)

        # make sample instances
        self.reference_sample_instance.rt_cal_dict = \
              self.reference_sample_instance.reverse_rt_cal_dict = {}
        self.experiment.all_samples.append(self.reference_sample_instance)
        for sid in self.experiment.valid_sample_ids:
            if sid != self.experiment.reference_sample_id:
                SM = SimpleSample(self.experiment.sample_registry[sid],
                    experiment=self.experiment, database_mode=self.experiment.database_mode, 
                    mode=self.experiment.mode
                    )
                self.experiment.all_samples.append(SM)


    def _initiate_mass_grid(self):
        '''
        Initiate self.MassGrid as pandas DataFrame.
        The reference sample is used to populate first m/z column.
        This sets 1st instance into self.experiment.all_samples.

        Updates
        -------
        self._mz_landmarks_ : landmark m/z values that match to 13C/12C pattern
        self.MassGrid : DataFrame with reference sample as first entry
        self.experiment.all_samples : adding 1st sample (reference)
        '''
        reference_sample = self.reference_sample_instance
        reference_sample.rt_cal_dict = reference_sample.reverse_rt_cal_dict = {}
        ref_list_mass_tracks = reference_sample.list_mass_tracks

        self._mz_landmarks_ = reference_sample._mz_landmarks_
        reference_mzlist = [ x['mz'] for x in ref_list_mass_tracks ]
        # setting up DataFrame for MassGrid
        # not forcing dtype on DataFrame, to avoid unreported errors; convert to int when using MassGrid
        self.MassGrid = pd.DataFrame(
            np.full((len(reference_mzlist), 1+self._number_of_samples_), None),
            columns=['mz'] + self.list_sample_names,
        )
        # Add ref mz as a column to MassGrid; ref mzlist will be dynamic updated in MassGrid["mz"]
        self.MassGrid['mz'] = reference_mzlist
        self.MassGrid[ reference_sample.name ] = [ x['id_number'] for x in ref_list_mass_tracks ]
        self.experiment.all_samples.append(reference_sample)


    def add_sample(self, sample, database_cursor=None):
        '''
        This adds a sample to MassGrid, including the m/z alignment of the sample against the 
        existing reference m/z values in the MassGrid.

        Parameters
        ----------
        sample : instance of SimpleSample class.
        database_cursor : Not used now.

        Updates
        -------
        self._mz_landmarks_ : landmark m/z values that match to 13C/12C and Na/H patterns
        self.MassGrid : DataFrame with reference sample as first entry
        self.experiment.all_samples : adding this sample 
        '''
        print("Adding sample to MassGrid,", sample.name)
        mzlist = [x[0] for x in sample.track_mzs]
        new_reference_mzlist, new_reference_map2, updated_REF_landmarks, _r = \
            landmark_guided_mapping(
                list(self.MassGrid['mz']), self._mz_landmarks_, mzlist, sample._mz_landmarks_
                )

        NewGrid = pd.DataFrame(
            np.full((len(new_reference_mzlist), 1+self._number_of_samples_), None),
            columns=['mz'] + self.list_sample_names,
        )
        NewGrid[ :self.MassGrid.shape[0]] = self.MassGrid
        NewGrid['mz'] = new_reference_mzlist
        NewGrid[ sample.name ] = new_reference_map2
        self.MassGrid = NewGrid
        self._mz_landmarks_ = updated_REF_landmarks
        sample.mz_calibration_ratio = _r            # not used now
        
        self.experiment.all_samples.append(sample)


    def bin_track_mzs(self, tl, reference_id):
        '''
        Bin all track m/z values into centroids via clustering, to be used to build massGrid.

        Parameters
        ----------
        tl : sorted list of all track m/z values in experiment, [(m/z, track_id, sample_id), ...]
        reference_id: the sample_id of reference sample. Not used now.
        
        Returns
        -------
        list of bins: [ (mean_mz, [(), (), ...]), (mean_mz, [(), (), ...]), ... ]

        Note:
            Because the range of each bin cannot be larger than mz_tolerance, 
            and mass tracks in each sample cannot overlap within mz_tolerance,
            multiple entries from the same sample in same bin will not happen.
            Similar to nearest neighbor (NN) clustering used in initial mass track construction.
        '''
        def __get_bin__(bin_data_tuples):
            return (np.median([x[0] for x in bin_data_tuples]), bin_data_tuples)

        tol_ = 0.000001 * self.experiment.parameters['mz_tolerance_ppm']
        bins_of_bins = []
        tmp = [tl[0]]
        for ii in range(1, len(tl)):
            _delta = tl[ii][0] - tl[ii-1][0]
            # bin adjacent tuples if they are within ppm tolerance
            if _delta < tol_ * tl[ii-1][0]:
                tmp.append(tl[ii])
            else:
                bins_of_bins.append(tmp)
                tmp = [tl[ii]]
        bins_of_bins.append(tmp)
        good_bins = []
        for bin_data_tuples in bins_of_bins:
            mz_range = bin_data_tuples[-1][0] - bin_data_tuples[0][0]
            mz_tolerance = bin_data_tuples[0][0] * tol_
            # important: double tol_ range here as mean_mz falls in single tol_
            if mz_range < mz_tolerance * 2:
                good_bins.append( __get_bin__(bin_data_tuples) )

            else:
                good_bins += [__get_bin__(C) for C in nn_cluster_by_mz_seeds(
                    bin_data_tuples, mz_tolerance)]

        return good_bins


    def join(self, M2):
        '''
        Placeholder. Future option to join with another MassGrid via a common reference.
        '''
        pass


class CompositeMap:
    '''
    Each experiment is summarized into a CompositeMap (CMAP), as a master feature map.
    The use of CompositeMap also facilitates data visualization and exploration.
    Related concepts:
    i) MassGrid: a matrix for recording correspondence of mass tracks to each sample 
    ii) FeatureList: list of feature definitions, i.e. elution peaks defined on composite mass tracks.
    iii) FeatureTable: a matrix for feature intensities per sample.
    '''
    def __init__(self, experiment):
        '''
        Composite map of mass tracks and features, with pointers to individual samples.
        '''
        self.experiment = experiment
        self._number_of_samples_ = experiment.number_of_samples
        self.list_sample_names = [experiment.sample_registry[ii]['name'] 
                                  for ii in experiment.valid_sample_ids]

        # designated reference sample; all RT is aligned to this sample
        self.reference_sample_instance = self.reference_sample = \
            self.get_reference_sample_instance(experiment.reference_sample_id)
        self.rt_length = self.experiment.number_scans
        self.dict_scan_rtime = self.get_reference_rtimes(self.rt_length)
        self.max_ref_rtime = self.dict_scan_rtime[self.rt_length-1]

        self.MassGrid = None                        # will be pandas DataFrame, = MassGrid.MassGrid
        self.FeatureTable = None
        self.FeatureList = []

        self._mz_landmarks_ = []                    # m/z landmarks as index numbers
        self.good_reference_landmark_peaks = []     # used for RT alignment and m/z calibration to DB
        # self.reference_mzdict = {}
        self.composite_mass_tracks = {}             # following MassGrid indices

    def get_reference_sample_instance(self, reference_sample_id):
        '''
        Wraps the reference_sample into a SimpleSample instance, so that
        it have same behaivors as other samples.

        Returns
        -------
        instance of SimpleSample class for the reference_sample.
        '''
        SM = SimpleSample(self.experiment.sample_registry[reference_sample_id],
                experiment=self.experiment, database_mode=self.experiment.database_mode, 
                mode=self.experiment.mode,
                is_reference=True)
        SM.list_mass_tracks = SM.get_masstracks_and_anchors()
        return SM

    def get_reference_rtimes(self, rt_length):
        '''
        Extrapolate retention time on self.reference_sample_instance to max scan number in the experiment.
        This will be used to calculate retention time in the end, as intermediary steps use scan numbers.

        Returns
        -------
        dictionary of scan number to retetion time in the reference_sample.
        '''
        X, Y = self.reference_sample.rt_numbers, self.reference_sample.list_retention_time
        interf = interpolate.interp1d(X, Y, fill_value="extrapolate")
        newX = range(rt_length)
        newY = interf(newX)
        return dict(zip(newX, newY))

    def construct_mass_grid(self):
        '''
        Constructing MassGrid for the whole experiment. 
        If the sample number is no more than a predefined parameter ('project_sample_number_small', default 10), 
        this is considered a small study and a pairwise alignment is performed.
        See `MassGrid.build_grid_sample_wise`, `MassGrid.add_sample`.
        Else, for a larger study, the mass alignment is performed by the same NN clustering method 
        that is used in initial mass track construction. 
        See `MassGrid.build_grid_by_centroiding`, `MassGrid.bin_track_mzs`.
        
        Updates
        -------
        self._mz_landmarks_ : landmark m/z values that match to 13C/12C and Na/H patterns
        self.MassGrid : DataFrame with reference sample as first entry. Use sample name as column identifiers.
        
        Note:
            Number of samples dictate workflow: 
            build_grid_by_centroiding is fast, but build_grid_sample_wise is used for small studies 
            to compensate limited size for statistical distribution.
            All mass tracks are included at this stage, regardless if peaks are detected, because
            peak detection will be an improved process on the composite tracks.
        '''
        print("Constructing MassGrid, ...")
        MG = MassGrid( self, self.experiment )
        if self._number_of_samples_ <= self.experiment.parameters['project_sample_number_small']:
            MG.build_grid_sample_wise()
        else:
            MG.build_grid_by_centroiding()
           
        self.MassGrid = MG.MassGrid
        self._mz_landmarks_ = MG._mz_landmarks_

    def mock_rentention_alignment(self):
        '''
        Create empty mapping dictionaries if the RT alignment fails, e.g. for blank or exogenous samples.
        '''
        for sample in self.experiment.all_samples[1:]:      # first sample is reference
            sample.rt_cal_dict, sample.reverse_rt_cal_dict = {}, {}


    def build_composite_tracks(self):
        '''
        Perform RT calibration then make composite tracks.

        Updates
        -------
        self.good_reference_landmark_peaks : [{'ref_id_num': 99, 'apex': 211, 'height': 999999}, ...]
        self.composite_mass_tracks : list of composite mass tracks in this experiment.
        sample.rt_cal_dict and sample.reverse_rt_cal_dict for all samples.

        Note:
            See calibrate_sample_RT for details in RT alignment. 
        '''
        print("\nBuilding composite mass tracks and calibrating retention time ...\n")

        cal_min_peak_height = self.experiment.parameters['cal_min_peak_height']
        MIN_PEAK_NUM = self.experiment.parameters['peak_number_rt_calibration']
        self.good_reference_landmark_peaks = self.set_RT_reference(cal_min_peak_height)
        
        mzDict = dict(self.MassGrid['mz'])
        mzlist = list(self.MassGrid.index)                          # this gets indices as keys, per mass track
        basetrack = np.zeros(self.rt_length, dtype=np.int64)        # self.rt_length defines max rt number
        _comp_dict = {}
        for k in mzlist: 
            _comp_dict[k] = basetrack.copy()

        for SM in self.experiment.all_samples:
            print("   ", SM.name)
            list_mass_tracks = SM.get_masstracks_and_anchors()

            if self.experiment.parameters['rt_align_on'] and not SM.is_reference:
                self.calibrate_sample_RT(SM, list_mass_tracks, 
                                        cal_min_peak_height=cal_min_peak_height, 
                                        MIN_PEAK_NUM=MIN_PEAK_NUM)

            for k in mzlist:
                ref_index = self.MassGrid[SM.name][k]
                if not pd.isna(ref_index): # ref_index can be NA 
                    _comp_dict[k] += remap_intensity_track( 
                        list_mass_tracks[int(ref_index)]['intensity'],  
                        basetrack.copy(), SM.rt_cal_dict 
                        )

        result = {}
        for k,v in _comp_dict.items():
            result[k] = { 'id_number': k, 'mz': mzDict[k], 'intensity': v }

        self.composite_mass_tracks = result

    def calibrate_sample_RT_by_standards(self, sample, ):
        '''
        Placeholder, to add RT calibration based on spikie-in compound standards.
        '''
        pass


    def calibrate_sample_RT(self, 
                                sample, 
                                list_mass_tracks,
                                calibration_fuction=rt_lowess_calibration, 
                                cal_min_peak_height=100000,
                                MIN_PEAK_NUM=15):
        '''
        Calibrate/align retention time per sample.

        Parameters
        ----------
        sample : instance of SimpleSample class
        list_mass_tracks : list of mass tracks in sample. 
            This may not be kept in memeory with the sample instance, thus require retrieval.
        calibration_fuction : RT calibration fuction to use, default to rt_lowess_calibration.
        cal_min_peak_height : minimal height required for a peak to be used for calibration.
            Only high-quality peaks unique in each mass track are used for calibration.
        MIN_PEAK_NUM : minimal number of peaks required for calibration. Abort if not met.

        Updates
        -------
        sample.rt_cal_dict : dictionary converting scan number in sample_rt_numbers to 
            calibrated integer values in self.reference_sample.
            Range matched. Only changed numbers are kept for efficiency.
        sample.reverse_rt_cal_dict : dictionary from ref RT scan numbers to sample RT scan numbers. 
            Range matched. Only changed numbers are kept for efficiency.

        Note:
            This is based on a set of unambiguous peaks: quich peak detection on anchor mass trakcs, 
            and peaks that are unique to each track are used for RT alignment.
            Only numbers different btw two samples are kept in the dictionaries for computing efficiency.
            When calibration_fuction fails, e.g. inf on lowess_predicted,
            it is assumed that this sample is not amendable to computational alignment,
            and the sample will be attached later without adjusting retention time.
            To consider to enforce good_landmark_peaks to cover RT range evenly in the future.
        '''
        candidate_landmarks = [self.MassGrid[sample.name].values[
                                p['ref_id_num']] for p in 
                                self.good_reference_landmark_peaks] # contains NaN
        good_landmark_peaks, selected_reference_landmark_peaks = [], []

        for jj in range(len(self.good_reference_landmark_peaks)):
            ii = candidate_landmarks[jj]
            if not pd.isna(ii):
                ii = int(ii)
                this_mass_track = list_mass_tracks[ii]
                Upeak = quick_detect_unique_elution_peak(this_mass_track['intensity'], 
                            min_peak_height=cal_min_peak_height, 
                            min_fwhm=3, min_prominence_threshold_ratio=0.2)
                if Upeak:
                    Upeak.update({'ref_id_num': ii})
                    good_landmark_peaks.append(Upeak)
                    selected_reference_landmark_peaks.append(self.good_reference_landmark_peaks[jj])

        _NN, _CALIBRATED = len(good_landmark_peaks), False
        # only do RT calibration if MIN_PEAK_NUM is met
        if _NN >  MIN_PEAK_NUM:
            try:
                sample.rt_cal_dict, sample.reverse_rt_cal_dict = calibration_fuction( 
                                            good_landmark_peaks, selected_reference_landmark_peaks, 
                                            sample.rt_numbers, self.reference_sample.rt_numbers, )
                _CALIBRATED = True
            except:         # ValueError:
                pass
        if not _CALIBRATED:
                sample.rt_cal_dict, sample.reverse_rt_cal_dict =  {}, {}
                print("    ~warning~ Faluire in retention time alignment (%d); %s is used without alignment." 
                                            %( _NN, sample.name))
                

    def set_RT_reference(self, cal_peak_intensity_threshold=100000):
        '''
        Start with the referecne samples, usually set for a sample of most landmark mass tracks.
        Do a quick peak detection for good peaks; use high selectivity m/z to avoid ambiguity 
        in peak definitions.

        Returns
        ------- 
        good_reference_landmark_peaks: [{'ref_id_num': 99, 'apex': 211, 'height': 999999}, ...]
        '''
        selectivities = calculate_selectivity( self.MassGrid['mz'][self._mz_landmarks_], 
                                                self.experiment.parameters['mz_tolerance_ppm'])
        good_reference_landmark_peaks = []
        ref_list_mass_tracks = self.reference_sample.list_mass_tracks
        for ii in range(len(self._mz_landmarks_)):
            if selectivities[ii] > 0.99:
                ref_ii = self.MassGrid[self.reference_sample.name][self._mz_landmarks_[ii]]
                if ref_ii and not pd.isna(ref_ii):
                    this_mass_track = ref_list_mass_tracks[ int(ref_ii) ]
                    Upeak = quick_detect_unique_elution_peak(this_mass_track['intensity'], 
                                min_peak_height=cal_peak_intensity_threshold, 
                                min_fwhm=3, min_prominence_threshold_ratio=0.2)
                    if Upeak:
                        Upeak.update({'ref_id_num': self._mz_landmarks_[ii]}) # as in MassGrid index
                        good_reference_landmark_peaks.append(Upeak)

        return good_reference_landmark_peaks


    def global_peak_detection(self):
        '''
        Detects elution peaks on composite mass tracks, resulting to a list of features.
        Using peaks.batch_deep_detect_elution_peaks for parallel processing.

        Updates
        -------
        self.FeatureList : a list of JSON peaks
        self.FeatureTable : a pandas dataframe for features across all samples.

        Note:
            Because the composite mass tracks ar summarized on all samples, 
            the resulting elution peaks are really features at the experiment level.
            Peak area and height are cumulated from all samples, 
            not average because some peaks are in only few samples.
        '''
        print("\nPeak detection on %d composite mass tracks, ...\n" %len(self.composite_mass_tracks))

        self.FeatureList = batch_deep_detect_elution_peaks(
            self.composite_mass_tracks.values(), 
            self.experiment.number_scans, self.experiment.parameters
        )
        ii = 0
        for peak in self.FeatureList:
            ii += 1
            peak['id_number'] = 'F'+str(ii)
            # convert scan numbers to rtime
            try:
                peak['rtime'] = self.dict_scan_rtime[peak['apex']]
            except KeyError:
                peak['rtime'] = self.max_ref_rtime                # imputed value set at max rtime
                print("Feature rtime out of bound - ", peak['id_number'], peak['apex'])
            try:
                peak['rtime_left_base'], peak['rtime_right_base'] = self.dict_scan_rtime[
                                peak['left_base']], self.dict_scan_rtime[peak['right_base']]
            except KeyError:
                print("Feature rtime out of bound on", peak['id_number'], 
                      (peak['apex'], peak['left_base'], peak['right_base']))

        self.generate_feature_table()


    def generate_feature_table(self):
        '''
        Initiate and populate self.FeatureTable, each sample per column in dataframe.
        '''
        FeatureTable = pd.DataFrame(self.FeatureList)
        for SM in self.experiment.all_samples:
            FeatureTable[SM.name] = self.extract_features_per_sample(SM)

        self.FeatureTable = FeatureTable


    def extract_features_per_sample(self, sample):
        '''
        Extract and return peak area values in a sample, 
        based on the start and end positions defined in self.FeatureList.
        A peak area could be 0 if no real peak is present for a feature in this sample.

        Parameters
        ----------
        sample : instance of SimpleSample class.

        Returns
        ------- 
        A list of peak area values, for all features in a sample.
        '''
        fList = []
        mass_track_map = self.MassGrid[sample.name]
        list_mass_tracks = sample.get_masstracks_and_anchors()
        for peak in self.FeatureList:
            track_number = mass_track_map[peak['parent_masstrack_id']]
            peak_area = 0
            if not pd.isna(track_number):           # watch out dtypes
                mass_track = list_mass_tracks[ int(track_number) ]
                # watch for range due to calibration/conversion.
                left_base = sample.reverse_rt_cal_dict.get(peak['left_base'], peak['left_base'])
                right_base = sample.reverse_rt_cal_dict.get(peak['right_base'], peak['right_base'])
                peak_area = mass_track['intensity'][left_base: right_base+1].sum()

            fList.append( peak_area )

        return fList
