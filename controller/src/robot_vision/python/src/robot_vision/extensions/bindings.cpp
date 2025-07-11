/*
 * Copyright (C) 2024 Intel Corporation
 *
 * This software and the related documents are Intel copyrighted materials,
 * and your use of them is governed by the express license under which they
 * were provided to you ("License"). Unless the License provides otherwise,
 * you may not use, modify, copy, publish, distribute, disclose or transmit
 * this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the License.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <rv/tracking/transform.hpp>
#include <pybind11/eigen.h>
#include <rv/tracking/point.h>
#include <rv/tracking/rectangle.h>

namespace py = pybind11;


PYBIND11_MODULE(cpp_transform, m) {

    // CameraIntrinsics bindings
    py::class_<rv::tracking::CameraIntrinsics, std::shared_ptr<rv::tracking::CameraIntrinsics>>(m, "CameraIntrinsics")
        .def(py::init<const std::vector<double>&, const std::vector<double>&, const std::vector<int>&>(),
             py::arg("intrinsics"), py::arg("distortion"), py::arg("resolution"))
        .def("unwarp", &rv::tracking::CameraIntrinsics::unwarp, py::arg("image"))
        .def("infer3DCoordsFrom2DDetection", &rv::tracking::CameraIntrinsics::infer3DCoordsFrom2DDetection,
             py::arg("coords"), py::arg("distance") = std::numeric_limits<double>::quiet_NaN())

    ;
}
