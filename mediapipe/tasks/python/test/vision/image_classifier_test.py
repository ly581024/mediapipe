# Copyright 2022 The MediaPipe Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for image classifier."""

import enum
import os
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized

import numpy as np

from mediapipe.python._framework_bindings import image
from mediapipe.tasks.python.components.containers import category
from mediapipe.tasks.python.components.containers import classifications as classifications_module
from mediapipe.tasks.python.components.containers import rect
from mediapipe.tasks.python.components.processors import classifier_options
from mediapipe.tasks.python.core import base_options as base_options_module
from mediapipe.tasks.python.test import test_utils
from mediapipe.tasks.python.vision import image_classifier
from mediapipe.tasks.python.vision.core import vision_task_running_mode

_NormalizedRect = rect.NormalizedRect
_BaseOptions = base_options_module.BaseOptions
_ClassifierOptions = classifier_options.ClassifierOptions
_Category = category.Category
_ClassificationEntry = classifications_module.ClassificationEntry
_Classifications = classifications_module.Classifications
_ClassificationResult = classifications_module.ClassificationResult
_Image = image.Image
_ImageClassifier = image_classifier.ImageClassifier
_ImageClassifierOptions = image_classifier.ImageClassifierOptions
_RUNNING_MODE = vision_task_running_mode.VisionTaskRunningMode

_MODEL_FILE = 'mobilenet_v2_1.0_224.tflite'
_IMAGE_FILE = 'burger.jpg'
_ALLOW_LIST = ['cheeseburger', 'guacamole']
_DENY_LIST = ['cheeseburger']
_SCORE_THRESHOLD = 0.5
_MAX_RESULTS = 3
_TEST_DATA_DIR = 'mediapipe/tasks/testdata/vision'


def _generate_empty_results(timestamp_ms: int) -> _ClassificationResult:
  return _ClassificationResult(classifications=[
      _Classifications(
          entries=[
              _ClassificationEntry(categories=[], timestamp_ms=timestamp_ms)
          ],
          head_index=0,
          head_name='probability')
  ])


def _generate_burger_results(timestamp_ms: int) -> _ClassificationResult:
  return _ClassificationResult(classifications=[
      _Classifications(
          entries=[
              _ClassificationEntry(
                  categories=[
                      _Category(
                          index=934,
                          score=0.793959,
                          display_name='',
                          category_name='cheeseburger'),
                      _Category(
                          index=932,
                          score=0.0273929,
                          display_name='',
                          category_name='bagel'),
                      _Category(
                          index=925,
                          score=0.0193408,
                          display_name='',
                          category_name='guacamole'),
                      _Category(
                          index=963,
                          score=0.00632786,
                          display_name='',
                          category_name='meat loaf')
                  ],
                  timestamp_ms=timestamp_ms)
          ],
          head_index=0,
          head_name='probability')
  ])


def _generate_soccer_ball_results(timestamp_ms: int) -> _ClassificationResult:
  return _ClassificationResult(classifications=[
      _Classifications(
          entries=[
              _ClassificationEntry(
                  categories=[
                      _Category(
                          index=806,
                          score=0.996527,
                          display_name='',
                          category_name='soccer ball')
                  ],
                  timestamp_ms=timestamp_ms)
          ],
          head_index=0,
          head_name='probability')
  ])


class ModelFileType(enum.Enum):
  FILE_CONTENT = 1
  FILE_NAME = 2


class ImageClassifierTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.test_image = _Image.create_from_file(
        test_utils.get_test_data_path(
            os.path.join(_TEST_DATA_DIR, _IMAGE_FILE)))
    self.model_path = test_utils.get_test_data_path(
        os.path.join(_TEST_DATA_DIR, _MODEL_FILE))

  def test_create_from_file_succeeds_with_valid_model_path(self):
    # Creates with default option and valid model file successfully.
    with _ImageClassifier.create_from_model_path(self.model_path) as classifier:
      self.assertIsInstance(classifier, _ImageClassifier)

  def test_create_from_options_succeeds_with_valid_model_path(self):
    # Creates with options containing model file successfully.
    base_options = _BaseOptions(model_asset_path=self.model_path)
    options = _ImageClassifierOptions(base_options=base_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      self.assertIsInstance(classifier, _ImageClassifier)

  def test_create_from_options_fails_with_invalid_model_path(self):
    # Invalid empty model path.
    with self.assertRaisesRegex(
        ValueError,
        r"ExternalFile must specify at least one of 'file_content', "
        r"'file_name', 'file_pointer_meta' or 'file_descriptor_meta'."):
      base_options = _BaseOptions(model_asset_path='')
      options = _ImageClassifierOptions(base_options=base_options)
      _ImageClassifier.create_from_options(options)

  def test_create_from_options_succeeds_with_valid_model_content(self):
    # Creates with options containing model content successfully.
    with open(self.model_path, 'rb') as f:
      base_options = _BaseOptions(model_asset_buffer=f.read())
      options = _ImageClassifierOptions(base_options=base_options)
      classifier = _ImageClassifier.create_from_options(options)
      self.assertIsInstance(classifier, _ImageClassifier)

  @parameterized.parameters(
      (ModelFileType.FILE_NAME, 4, _generate_burger_results(0)),
      (ModelFileType.FILE_CONTENT, 4, _generate_burger_results(0)))
  def test_classify(self, model_file_type, max_results,
                    expected_classification_result):
    # Creates classifier.
    if model_file_type is ModelFileType.FILE_NAME:
      base_options = _BaseOptions(model_asset_path=self.model_path)
    elif model_file_type is ModelFileType.FILE_CONTENT:
      with open(self.model_path, 'rb') as f:
        model_content = f.read()
      base_options = _BaseOptions(model_asset_buffer=model_content)
    else:
      # Should never happen
      raise ValueError('model_file_type is invalid.')

    custom_classifier_options = _ClassifierOptions(max_results=max_results)
    options = _ImageClassifierOptions(
        base_options=base_options, classifier_options=custom_classifier_options)
    classifier = _ImageClassifier.create_from_options(options)

    # Performs image classification on the input.
    image_result = classifier.classify(self.test_image)
    # Comparing results.
    test_utils.assert_proto_equals(self, image_result.to_pb2(),
                                   expected_classification_result.to_pb2())
    # Closes the classifier explicitly when the classifier is not used in
    # a context.
    classifier.close()

  @parameterized.parameters(
      (ModelFileType.FILE_NAME, 4, _generate_burger_results(0)),
      (ModelFileType.FILE_CONTENT, 4, _generate_burger_results(0)))
  def test_classify_in_context(self, model_file_type, max_results,
                               expected_classification_result):
    if model_file_type is ModelFileType.FILE_NAME:
      base_options = _BaseOptions(model_asset_path=self.model_path)
    elif model_file_type is ModelFileType.FILE_CONTENT:
      with open(self.model_path, 'rb') as f:
        model_content = f.read()
      base_options = _BaseOptions(model_asset_buffer=model_content)
    else:
      # Should never happen
      raise ValueError('model_file_type is invalid.')

    custom_classifier_options = _ClassifierOptions(max_results=max_results)
    options = _ImageClassifierOptions(
        base_options=base_options, classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Performs image classification on the input.
      image_result = classifier.classify(self.test_image)
      # Comparing results.
      test_utils.assert_proto_equals(self, image_result.to_pb2(),
                                     expected_classification_result.to_pb2())

  def test_classify_succeeds_with_region_of_interest(self):
    base_options = _BaseOptions(model_asset_path=self.model_path)
    custom_classifier_options = _ClassifierOptions(max_results=1)
    options = _ImageClassifierOptions(
        base_options=base_options, classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Load the test image.
      test_image = _Image.create_from_file(
          test_utils.get_test_data_path(
              os.path.join(_TEST_DATA_DIR, 'multi_objects.jpg')))
      # NormalizedRect around the soccer ball.
      roi = _NormalizedRect(
          x_center=0.532, y_center=0.521, width=0.164, height=0.427)
      # Performs image classification on the input.
      image_result = classifier.classify(test_image, roi)
      # Comparing results.
      test_utils.assert_proto_equals(self, image_result.to_pb2(),
                                     _generate_soccer_ball_results(0).to_pb2())

  def test_score_threshold_option(self):
    custom_classifier_options = _ClassifierOptions(
        score_threshold=_SCORE_THRESHOLD)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Performs image classification on the input.
      image_result = classifier.classify(self.test_image)
      classifications = image_result.classifications

      for classification in classifications:
        for entry in classification.entries:
          score = entry.categories[0].score
          self.assertGreaterEqual(
              score, _SCORE_THRESHOLD,
              f'Classification with score lower than threshold found. '
              f'{classification}')

  def test_max_results_option(self):
    custom_classifier_options = _ClassifierOptions(
        score_threshold=_SCORE_THRESHOLD)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Performs image classification on the input.
      image_result = classifier.classify(self.test_image)
      categories = image_result.classifications[0].entries[0].categories

      self.assertLessEqual(
          len(categories), _MAX_RESULTS, 'Too many results returned.')

  def test_allow_list_option(self):
    custom_classifier_options = _ClassifierOptions(
        category_allowlist=_ALLOW_LIST)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Performs image classification on the input.
      image_result = classifier.classify(self.test_image)
      classifications = image_result.classifications

      for classification in classifications:
        for entry in classification.entries:
          label = entry.categories[0].category_name
          self.assertIn(label, _ALLOW_LIST,
                        f'Label {label} found but not in label allow list')

  def test_deny_list_option(self):
    custom_classifier_options = _ClassifierOptions(category_denylist=_DENY_LIST)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Performs image classification on the input.
      image_result = classifier.classify(self.test_image)
      classifications = image_result.classifications

      for classification in classifications:
        for entry in classification.entries:
          label = entry.categories[0].category_name
          self.assertNotIn(label, _DENY_LIST,
                           f'Label {label} found but in deny list.')

  def test_combined_allowlist_and_denylist(self):
    # Fails with combined allowlist and denylist
    with self.assertRaisesRegex(
        ValueError,
        r'`category_allowlist` and `category_denylist` are mutually '
        r'exclusive options.'):
      custom_classifier_options = _ClassifierOptions(
          category_allowlist=['foo'], category_denylist=['bar'])
      options = _ImageClassifierOptions(
          base_options=_BaseOptions(model_asset_path=self.model_path),
          classifier_options=custom_classifier_options)
      with _ImageClassifier.create_from_options(options) as unused_classifier:
        pass

  def test_empty_classification_outputs(self):
    custom_classifier_options = _ClassifierOptions(score_threshold=1)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Performs image classification on the input.
      image_result = classifier.classify(self.test_image)
      self.assertEmpty(image_result.classifications[0].entries[0].categories)

  def test_missing_result_callback(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.LIVE_STREAM)
    with self.assertRaisesRegex(ValueError,
                                r'result callback must be provided'):
      with _ImageClassifier.create_from_options(options) as unused_classifier:
        pass

  @parameterized.parameters((_RUNNING_MODE.IMAGE), (_RUNNING_MODE.VIDEO))
  def test_illegal_result_callback(self, running_mode):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=running_mode,
        result_callback=mock.MagicMock())
    with self.assertRaisesRegex(ValueError,
                                r'result callback should not be provided'):
      with _ImageClassifier.create_from_options(options) as unused_classifier:
        pass

  def test_calling_classify_for_video_in_image_mode(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.IMAGE)
    with _ImageClassifier.create_from_options(options) as classifier:
      with self.assertRaisesRegex(ValueError,
                                  r'not initialized with the video mode'):
        classifier.classify_for_video(self.test_image, 0)

  def test_calling_classify_async_in_image_mode(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.IMAGE)
    with _ImageClassifier.create_from_options(options) as classifier:
      with self.assertRaisesRegex(ValueError,
                                  r'not initialized with the live stream mode'):
        classifier.classify_async(self.test_image, 0)

  def test_calling_classify_in_video_mode(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.VIDEO)
    with _ImageClassifier.create_from_options(options) as classifier:
      with self.assertRaisesRegex(ValueError,
                                  r'not initialized with the image mode'):
        classifier.classify(self.test_image)

  def test_calling_classify_async_in_video_mode(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.VIDEO)
    with _ImageClassifier.create_from_options(options) as classifier:
      with self.assertRaisesRegex(ValueError,
                                  r'not initialized with the live stream mode'):
        classifier.classify_async(self.test_image, 0)

  def test_classify_for_video_with_out_of_order_timestamp(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.VIDEO)
    with _ImageClassifier.create_from_options(options) as classifier:
      unused_result = classifier.classify_for_video(self.test_image, 1)
      with self.assertRaisesRegex(
          ValueError, r'Input timestamp must be monotonically increasing'):
        classifier.classify_for_video(self.test_image, 0)

  def test_classify_for_video(self):
    custom_classifier_options = _ClassifierOptions(max_results=4)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.VIDEO,
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      for timestamp in range(0, 300, 30):
        classification_result = classifier.classify_for_video(
            self.test_image, timestamp)
        test_utils.assert_proto_equals(
            self, classification_result.to_pb2(),
            _generate_burger_results(timestamp).to_pb2())

  def test_classify_for_video_succeeds_with_region_of_interest(self):
    custom_classifier_options = _ClassifierOptions(max_results=1)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.VIDEO,
        classifier_options=custom_classifier_options)
    with _ImageClassifier.create_from_options(options) as classifier:
      # Load the test image.
      test_image = _Image.create_from_file(
          test_utils.get_test_data_path(
              os.path.join(_TEST_DATA_DIR, 'multi_objects.jpg')))
      # NormalizedRect around the soccer ball.
      roi = _NormalizedRect(
          x_center=0.532, y_center=0.521, width=0.164, height=0.427)
      for timestamp in range(0, 300, 30):
        classification_result = classifier.classify_for_video(
            test_image, timestamp, roi)
        test_utils.assert_proto_equals(
            self, classification_result.to_pb2(),
            _generate_soccer_ball_results(timestamp).to_pb2())

  def test_calling_classify_in_live_stream_mode(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.LIVE_STREAM,
        result_callback=mock.MagicMock())
    with _ImageClassifier.create_from_options(options) as classifier:
      with self.assertRaisesRegex(ValueError,
                                  r'not initialized with the image mode'):
        classifier.classify(self.test_image)

  def test_calling_classify_for_video_in_live_stream_mode(self):
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.LIVE_STREAM,
        result_callback=mock.MagicMock())
    with _ImageClassifier.create_from_options(options) as classifier:
      with self.assertRaisesRegex(ValueError,
                                  r'not initialized with the video mode'):
        classifier.classify_for_video(self.test_image, 0)

  def test_classify_async_calls_with_illegal_timestamp(self):
    custom_classifier_options = _ClassifierOptions(max_results=4)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.LIVE_STREAM,
        classifier_options=custom_classifier_options,
        result_callback=mock.MagicMock())
    with _ImageClassifier.create_from_options(options) as classifier:
      classifier.classify_async(self.test_image, 100)
      with self.assertRaisesRegex(
          ValueError, r'Input timestamp must be monotonically increasing'):
        classifier.classify_async(self.test_image, 0)

  @parameterized.parameters((0, _generate_burger_results),
                            (1, _generate_empty_results))
  def test_classify_async_calls(self, threshold, expected_result_fn):
    observed_timestamp_ms = -1

    def check_result(result: _ClassificationResult, output_image: _Image,
                     timestamp_ms: int):
      test_utils.assert_proto_equals(self, result.to_pb2(),
                                     expected_result_fn(timestamp_ms).to_pb2())
      self.assertTrue(
          np.array_equal(output_image.numpy_view(),
                         self.test_image.numpy_view()))
      self.assertLess(observed_timestamp_ms, timestamp_ms)
      self.observed_timestamp_ms = timestamp_ms

    custom_classifier_options = _ClassifierOptions(
        max_results=4, score_threshold=threshold)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.LIVE_STREAM,
        classifier_options=custom_classifier_options,
        result_callback=check_result)
    with _ImageClassifier.create_from_options(options) as classifier:
      for timestamp in range(0, 300, 30):
        classifier.classify_async(self.test_image, timestamp)

  def test_classify_async_succeeds_with_region_of_interest(self):
    # Load the test image.
    test_image = _Image.create_from_file(
        test_utils.get_test_data_path(
            os.path.join(_TEST_DATA_DIR, 'multi_objects.jpg')))
    # NormalizedRect around the soccer ball.
    roi = _NormalizedRect(
        x_center=0.532, y_center=0.521, width=0.164, height=0.427)
    observed_timestamp_ms = -1

    def check_result(result: _ClassificationResult, output_image: _Image,
                     timestamp_ms: int):
      test_utils.assert_proto_equals(
          self, result.to_pb2(),
          _generate_soccer_ball_results(timestamp_ms).to_pb2())
      self.assertEqual(output_image.width, test_image.width)
      self.assertEqual(output_image.height, test_image.height)
      self.assertLess(observed_timestamp_ms, timestamp_ms)
      self.observed_timestamp_ms = timestamp_ms

    custom_classifier_options = _ClassifierOptions(max_results=1)
    options = _ImageClassifierOptions(
        base_options=_BaseOptions(model_asset_path=self.model_path),
        running_mode=_RUNNING_MODE.LIVE_STREAM,
        classifier_options=custom_classifier_options,
        result_callback=check_result)
    with _ImageClassifier.create_from_options(options) as classifier:
      for timestamp in range(0, 300, 30):
        classifier.classify_async(test_image, timestamp, roi)


if __name__ == '__main__':
  absltest.main()
