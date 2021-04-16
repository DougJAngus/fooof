"""Tests for fooof.objs.fit, including the model object and it's methods.

NOTES
-----
The tests here are not strong tests for accuracy.
They serve rather as 'smoke tests', for if anything fails completely.
"""

import numpy as np
from py.test import raises

from fooof.core.items import OBJ_DESC
from fooof.core.errors import FitError
from fooof.core.utils import group_three
from fooof.sim import gen_freqs, gen_power_spectrum
from fooof.data import ModelSettings, SpectrumMetaData, FitResults
from fooof.core.errors import DataError, NoDataError, InconsistentDataError

from fooof.tests.settings import TEST_DATA_PATH
from fooof.tests.tutils import get_tfm, plot_test

from fooof.objs.fit import *

###################################################################################################
###################################################################################################

def test_model_object():
    """Check model object initializes properly."""

    assert PSD(verbose=False)

def test_has_data(tfm):
    """Test the has_data property attribute, with and without model fits."""

    assert tfm.has_data

    ntfm = PSD()
    assert not ntfm.has_data

def test_has_model(tfm):
    """Test the has_model property attribute, with and without model fits."""

    assert tfm.has_model

    ntfm = PSD()
    assert not ntfm.has_model

def test_n_peaks(tfm):
    """Test the n_peaks property attribute."""

    assert tfm.n_peaks_

def test_fit_nk():
    """Test fit, no knee."""

    ap_params = [50, 2]
    gauss_params = [10, 0.5, 2, 20, 0.3, 4]
    nlv = 0.0025

    xs, ys = gen_power_spectrum([3, 50], ap_params, gauss_params, nlv)

    tfm = PSD(verbose=False)
    tfm.fit(xs, ys)

    # Check model results - aperiodic parameters
    assert np.allclose(ap_params, tfm.aperiodic_params_, [0.5, 0.1])

    # Check model results - gaussian parameters
    for ii, gauss in enumerate(group_three(gauss_params)):
        assert np.allclose(gauss, tfm.gaussian_params_[ii], [2.0, 0.5, 1.0])

def test_fit_nk_noise():
    """Test fit on noisy data, to make sure nothing breaks."""

    ap_params = [50, 2]
    gauss_params = [10, 0.5, 2, 20, 0.3, 4]
    nlv = 1.0

    xs, ys = gen_power_spectrum([3, 50], ap_params, gauss_params, nlv)

    tfm = PSD(max_n_peaks=8, verbose=False)
    tfm.fit(xs, ys)

    # No accuracy checking here - just checking that it ran
    assert tfm.has_model

def test_fit_knee():
    """Test fit, with a knee."""

    ap_params = [50, 10, 1]
    gauss_params = [10, 0.3, 2, 20, 0.1, 4, 60, 0.3, 1]
    nlv = 0.0025

    xs, ys = gen_power_spectrum([1, 150], ap_params, gauss_params, nlv)

    tfm = PSD(aperiodic_mode='knee', verbose=False)
    tfm.fit(xs, ys)

    # Check model results - aperiodic parameters
    assert np.allclose(ap_params, tfm.aperiodic_params_, [1, 2, 0.2])

    # Check model results - gaussian parameters
    for ii, gauss in enumerate(group_three(gauss_params)):
        assert np.allclose(gauss, tfm.gaussian_params_[ii], [2.0, 0.5, 1.0])

def test_fit_measures():
    """Test goodness of fit & error metrics, post model fitting."""

    tfm = PSD(verbose=False)

    # Hack fake data with known properties: total error magnitude 2
    tfm.power_spectrum = np.array([1, 2, 3, 4, 5])
    tfm.modeled_spectrum_ = np.array([1, 2, 5, 4, 5])

    # Check default goodness of fit and error measures
    tfm._calc_r_squared()
    assert np.isclose(tfm.r_squared_, 0.75757575)
    tfm._calc_error()
    assert np.isclose(tfm.error_, 0.4)

    # Check with alternative error fit approach
    tfm._calc_error(metric='MSE')
    assert np.isclose(tfm.error_, 0.8)
    tfm._calc_error(metric='RMSE')
    assert np.isclose(tfm.error_, np.sqrt(0.8))
    with raises(ValueError):
        tfm._calc_error(metric='BAD')

def test_checks():
    """Test various checks, errors and edge cases for model fitting.
    This tests all the input checking done in `_prepare_data`.
    """

    xs, ys = gen_power_spectrum([3, 50], [50, 2], [10, 0.5, 2])

    tfm = PSD(verbose=False)

    ## Check checks & errors done in `_prepare_data`

    # Check wrong data type error
    with raises(DataError):
        tfm.fit(list(xs), list(ys))

    # Check dimension error
    with raises(DataError):
        tfm.fit(xs, np.reshape(ys, [1, len(ys)]))

    # Check shape mismatch error
    with raises(InconsistentDataError):
        tfm.fit(xs[:-1], ys)

    # Check complex inputs error
    with raises(DataError):
        tfm.fit(xs, ys.astype('complex'))

    # Check trim_spectrum range
    tfm.fit(xs, ys, [3, 40])

    # Check freq of 0 issue
    xs, ys = gen_power_spectrum([3, 50], [50, 2], [10, 0.5, 2])
    tfm.fit(xs, ys)
    assert tfm.freqs[0] != 0

    # Check error if there is a post-logging inf or nan
    with raises(DataError):  # Double log (1) -> -inf
        tfm.fit(np.array([1, 2, 3]), np.log10(np.array([1, 2, 3])))
    with raises(DataError):  # Log (-1) -> NaN
        tfm.fit(np.array([1, 2, 3]), np.array([-1, 2, 3]))

    ## Check errors & errors done in `fit`

    # Check fit, and string report model error (no data / model fit)
    tfm = PSD(verbose=False)
    with raises(NoDataError):
        tfm.fit()

def test_load():
    """Test loading data into model object. Note: loads files from test_core_io."""

    # Test loading just results
    tfm = PSD(verbose=False)
    file_name_res = 'test_res'
    tfm.load(file_name_res, TEST_DATA_PATH)
    # Check that result attributes get filled
    for result in OBJ_DESC['results']:
        assert not np.all(np.isnan(getattr(tfm, result)))
    # Test that settings and data are None
    #   Except for aperiodic mode, which can be inferred from the data
    for setting in OBJ_DESC['settings']:
        if setting != 'aperiodic_mode':
            assert getattr(tfm, setting) is None
    assert getattr(tfm, 'power_spectrum') is None

    # Test loading just settings
    tfm = PSD(verbose=False)
    file_name_set = 'test_set'
    tfm.load(file_name_set, TEST_DATA_PATH)
    for setting in OBJ_DESC['settings']:
        assert getattr(tfm, setting) is not None
    # Test that results and data are None
    for result in OBJ_DESC['results']:
        assert np.all(np.isnan(getattr(tfm, result)))
    assert tfm.power_spectrum is None

    # Test loading just data
    tfm = PSD(verbose=False)
    file_name_dat = 'test_dat'
    tfm.load(file_name_dat, TEST_DATA_PATH)
    assert tfm.power_spectrum is not None
    # Test that settings and results are None
    for setting in OBJ_DESC['settings']:
        assert getattr(tfm, setting) is None
    for result in OBJ_DESC['results']:
        assert np.all(np.isnan(getattr(tfm, result)))

    # Test loading all elements
    tfm = PSD(verbose=False)
    file_name_all = 'test_all'
    tfm.load(file_name_all, TEST_DATA_PATH)
    for result in OBJ_DESC['results']:
        assert not np.all(np.isnan(getattr(tfm, result)))
    for setting in OBJ_DESC['settings']:
        assert getattr(tfm, setting) is not None
    for data in OBJ_DESC['data']:
        assert getattr(tfm, data) is not None
    for meta_dat in OBJ_DESC['meta_data']:
        assert getattr(tfm, meta_dat) is not None

def test_add_data():
    """Tests method to add data to model objects."""

    # This test uses it's own model object, to not add stuff to the global one
    tfm = get_tfm()

    # Test data for adding
    freqs, pows = np.array([1, 2, 3]), np.array([10, 10, 10])

    # Test adding data
    tfm.add_data(freqs, pows)
    assert tfm.has_data
    assert np.all(tfm.freqs == freqs)
    assert np.all(tfm.power_spectrum == np.log10(pows))

    # Test that prior data does not get cleared, when requesting not to clear
    tfm._reset_data_results(True, True, True)
    tfm.add_results(FitResults([1, 1], [10, 0.5, 0.5], 0.95, 0.02, [10, 0.5, 0.25]))
    tfm.add_data(freqs, pows, clear_results=False)
    assert tfm.has_data
    assert tfm.has_model

    # Test that prior data does get cleared, when requesting not to clear
    tfm._reset_data_results(True, True, True)
    tfm.add_data(freqs, pows, clear_results=True)
    assert tfm.has_data
    assert not tfm.has_model

def test_add_settings():
    """Tests method to add settings to model object."""

    # This test uses it's own model object, to not add stuff to the global one
    tfm = get_tfm()

    # Test adding settings
    settings = ModelSettings([1, 4], 6, 0, 2, 'fixed')
    tfm.add_settings(settings)
    for setting in OBJ_DESC['settings']:
        assert getattr(tfm, setting) == getattr(settings, setting)

def test_add_meta_data():
    """Tests method to add meta data to model object."""

    # This test uses it's own model object, to not add stuff to the global one
    tfm = get_tfm()

    # Test adding meta data
    meta_data = SpectrumMetaData([3, 40], 0.5)
    tfm.add_meta_data(meta_data)
    for meta_dat in OBJ_DESC['meta_data']:
        assert getattr(tfm, meta_dat) == getattr(meta_data, meta_dat)

def test_add_results():
    """Tests method to add results to model object."""

    # This test uses it's own model object, to not add stuff to the global one
    tfm = get_tfm()

    # Test adding results
    results = FitResults([1, 1], [10, 0.5, 0.5], 0.95, 0.02, [10, 0.5, 0.25])
    tfm.add_results(results)
    assert tfm.has_model
    for setting in OBJ_DESC['results']:
        assert getattr(tfm, setting) == getattr(results, setting.strip('_'))

def test_obj_gets(tfm):
    """Tests methods that return data objects.

    Checks: get_settings, get_meta_data, get_results
    """

    settings = tfm.get_settings()
    assert isinstance(settings, ModelSettings)
    meta_data = tfm.get_meta_data()
    assert isinstance(meta_data, SpectrumMetaData)
    results = tfm.get_results()
    assert isinstance(results, FitResults)

def test_get_params(tfm):
    """Test the get_params method."""

    for dname in ['aperiodic_params', 'aperiodic', 'peak_params', 'peak',
                  'error', 'r_squared', 'gaussian_params', 'gaussian']:
        assert np.any(tfm.get_params(dname))

        if dname == 'aperiodic_params' or dname == 'aperiodic':
            for dtype in ['offset', 'exponent']:
                assert np.any(tfm.get_params(dname, dtype))

        if dname == 'peak_params' or dname == 'peak':
            for dtype in ['CF', 'PW', 'BW']:
                assert np.any(tfm.get_params(dname, dtype))

def test_copy():
    """Test copy model object method."""

    tfm = PSD(verbose=False)
    ntfm = tfm.copy()

    assert tfm != ntfm

def test_prints(tfm):
    """Test methods that print (alias and pass through methods).

    Checks: print_settings, print_results, print_report_issue.
    """

    tfm.print_settings()
    tfm.print_results()
    tfm.print_report_issue()

@plot_test
def test_plot(tfm, skip_if_no_mpl):
    """Check the alias to plot spectra & model results."""

    tfm.plot()

def test_resets():
    """Check that all relevant data is cleared in the reset method."""

    # Note: uses it's own tfm, to not clear the global one
    tfm = get_tfm()

    tfm._reset_data_results(True, True, True)
    tfm._reset_internal_settings()

    for data in ['data', 'model_components']:
        for field in OBJ_DESC[data]:
            assert getattr(tfm, field) is None
    for field in OBJ_DESC['results']:
        assert np.all(np.isnan(getattr(tfm, field)))
    assert tfm.freqs is None and tfm.modeled_spectrum_ is None

def test_report(skip_if_no_mpl):
    """Check that running the top level model method runs."""

    tfm = PSD(verbose=False)

    tfm.report(*gen_power_spectrum([3, 50], [50, 2], [10, 0.5, 2, 20, 0.3, 4]))

    assert tfm

def test_fit_failure():
    """Test model fit failures."""

    ## Induce a runtime error, and check it runs through
    tfm = PSD(verbose=False)
    tfm._maxfev = 5

    tfm.fit(*gen_power_spectrum([3, 50], [50, 2], [10, 0.5, 2, 20, 0.3, 4]))

    # Check after failing out of fit, all results are reset
    for result in OBJ_DESC['results']:
        assert np.all(np.isnan(getattr(tfm, result)))

    ## Monkey patch to check errors in general
    #  This mimics the main fit-failure, without requiring bad data / waiting for it to fail.
    tfm = PSD(verbose=False)
    def raise_runtime_error(*args, **kwargs):
        raise FitError('Test-MonkeyPatch')
    tfm._fit_peaks = raise_runtime_error

    # Run a model fit - this should raise an error, but continue in try/except
    tfm.fit(*gen_power_spectrum([3, 50], [50, 2], [10, 0.5, 2, 20, 0.3, 4]))

    # Check after failing out of fit, all results are reset
    for result in OBJ_DESC['results']:
        assert np.all(np.isnan(getattr(tfm, result)))

def test_debug():
    """Test model object in debug mode, including with fit failures."""

    tfm = PSD(verbose=False)
    tfm._maxfev = 5

    tfm.set_debug_mode(True)
    assert tfm._debug is True

    with raises(FitError):
        tfm.fit(*gen_power_spectrum([3, 50], [50, 2], [10, 0.5, 2, 20, 0.3, 4]))

def test_check_data():
    """Test model fitting with check data mode turned off, including with NaN data."""

    tfm = PSD(verbose=False)

    tfm.set_check_data_mode(False)
    assert tfm._check_data is False

    # Add data, with check data turned off
    #   In check data mode, adding data with NaN should run
    freqs = gen_freqs([3, 50], 0.5)
    powers = np.ones_like(freqs) * np.nan
    tfm.add_data(freqs, powers)
    assert tfm.has_data

    # Model fitting should execute, but return a null model fit, given the NaNs, without failing
    tfm.fit()
    assert not tfm.has_model
