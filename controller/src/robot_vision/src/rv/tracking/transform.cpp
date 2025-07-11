#include <cmath>
#include <algorithm>
#include <rv/tracking/transform.hpp>

namespace rv {
namespace tracking {

CameraIntrinsics::CameraIntrinsics(const std::vector<double>& intrinsics,
                                   const std::vector<double>& distortion,
                                   const std::vector<int>& resolution)
    : distortion_(DISTORTION_SIZE, 0.0), resolution_(resolution) {
    std::vector<double> fov;
    std::vector<double> intr;
    if (intrinsics.size() == 1 || intrinsics.size() == 2) {
        fov = intrinsics;
    } else if (intrinsics.size() == 4) {
        // fx, fy, cx, cy
        intr = {intrinsics[0], 0.0, intrinsics[2],
                0.0, intrinsics[1], intrinsics[3],
                0.0, 0.0, 1.0};
    } else {
        throw std::runtime_error("Invalid intrinsics size");
    }
    if (!fov.empty()) {
        intrinsics_ = computeIntrinsicsFromFoV(resolution_, fov);
    } else {
        intrinsics_ = cv::Mat(3, 3, CV_64F);
        for (int i = 0; i < 3; ++i)
            for (int j = 0; j < 3; ++j)
                intrinsics_.at<double>(i, j) = intr[i * 3 + j];
    }
    setDistortion(distortion);
}

void CameraIntrinsics::setDistortion(const std::vector<double>& distortion) {
    if (distortion.empty()) {
        distortion_ = std::vector<double>(DISTORTION_SIZE, 0.0);
    } else {
        static const std::vector<int> valid_sizes = {4, 5, 8, 12, 14};
        if (std::find(valid_sizes.begin(), valid_sizes.end(), distortion.size()) == valid_sizes.end()) {
            throw std::runtime_error("Distortion vector must have 4, 5, 8, 12, or 14 elements");
        }
        distortion_ = distortion;
        if (distortion_.size() < DISTORTION_SIZE) {
            distortion_.resize(DISTORTION_SIZE, 0.0);
        }
    }
}

cv::Mat CameraIntrinsics::computeIntrinsicsFromFoV(const std::vector<int>& resolution, const std::vector<double>& fov) {
    if (resolution.size() != 2) {
        throw std::runtime_error("Resolution required to calculate intrinsics from field of view");
    }
    double cx = resolution[0] / 2.0;
    double cy = resolution[1] / 2.0;
    double d = std::sqrt(cx * cx + cy * cy);
    double fx = 0, fy = 0;
    if (fov.size() == 1) {
        fx = fy = d / std::tan(fov[0] * M_PI / 360.0);
    } else {
        fx = cx / std::tan(fov[0] * M_PI / 360.0);
        fy = cy / std::tan(fov[1] * M_PI / 360.0);
    }
    if (cx == 0 || cy == 0 || fx == 0 || fy == 0) {
        throw std::runtime_error("Invalid intrinsics computed from FoV");
    }
    cv::Mat mat = cv::Mat::eye(3, 3, CV_64F);
    mat.at<double>(0, 0) = fx;
    mat.at<double>(1, 1) = fy;
    mat.at<double>(0, 2) = cx;
    mat.at<double>(1, 2) = cy;
    return mat;
}

void CameraIntrinsics::createUndistortIntrinsics(const std::vector<int>& resolution) {
    undistort_intrinsics_ = intrinsics_.clone();
    undistort_intrinsics_.at<double>(0, 2) += resolution[0] / 2.0;
    undistort_intrinsics_.at<double>(1, 2) += resolution[1] / 2.0;
}

cv::Mat CameraIntrinsics::unwarp(const cv::Mat& image) {
    if (map1_.empty() || map2_.empty()) {
        int h = image.rows;
        int w = image.cols;
        createUndistortIntrinsics({w, h});
        cv::fisheye::initUndistortRectifyMap(
            intrinsics_, cv::Mat(distortion_).rowRange(0, 4), cv::Mat::eye(3, 3, CV_64F),
            undistort_intrinsics_, cv::Size(w * 2, h * 2), CV_16SC2, map1_, map2_);
    }
    cv::Mat new_image;
    cv::remap(image, new_image, map1_, map2_, cv::INTER_LINEAR, cv::BORDER_CONSTANT);
    if (crop_.empty()) {
        cv::Mat mask;
        cv::inRange(new_image, cv::Scalar(1, 1, 1), cv::Scalar(255, 255, 255), mask);
        std::vector<int> rows, cols;
        for (int i = 0; i < mask.rows; ++i) {
            if (cv::countNonZero(mask.row(i)) > 0) rows.push_back(i);
        }
        for (int j = 0; j < mask.cols; ++j) {
            if (cv::countNonZero(mask.col(j)) > 0) cols.push_back(j);
        }
        if (!rows.empty() && !cols.empty()) {
            int y1 = *std::min_element(rows.begin(), rows.end());
            int y2 = *std::max_element(rows.begin(), rows.end()) + 1;
            int x1 = *std::min_element(cols.begin(), cols.end());
            int x2 = *std::max_element(cols.begin(), cols.end()) + 1;
            crop_ = {y1, y2, x1, x2};
            // Cache intrinsics for unwarped image
            unwarp_intrinsics_ = intrinsics_.clone();
            int uh = y2 - y1;
            int uw = x2 - x1;
            unwarp_intrinsics_.at<double>(0, 2) = uw / 2.0;
            unwarp_intrinsics_.at<double>(1, 2) = uh / 2.0;
            unwarp_intrinsics_.at<double>(0, 0) = uw * unwarp_intrinsics_.at<double>(0, 0) / image.cols;
            unwarp_intrinsics_.at<double>(1, 1) = uh * unwarp_intrinsics_.at<double>(1, 1) / image.rows;
            new_image = new_image(cv::Range(crop_[0], crop_[1]), cv::Range(crop_[2], crop_[3]));
        }
    }
    return new_image;
}

cv::Mat CameraIntrinsics::pinholeUndistort(const cv::Mat& image) {
    // Undistort image using pinhole camera model
    bool nonzero = false;
    for (double v : distortion_) {
        if (std::abs(v) > 1e-8) {
            nonzero = true;
            break;
        }
    }
    if (nonzero) {
        int h = image.rows;
        int w = image.cols;
        cv::Mat map_x, map_y;
        cv::initUndistortRectifyMap(
            intrinsics_, cv::Mat(distortion_), cv::Mat(), intrinsics_,
            cv::Size(w, h), CV_32FC1, map_x, map_y);
        cv::Mat image_undistort;
        cv::remap(image, image_undistort, map_x, map_y, cv::INTER_LINEAR);
        return image_undistort;
    }
    return image;
}

Point CameraIntrinsics::infer3DCoordsFrom2DDetection(const Point& coords, double distance) {
    if (coords.is3D()) {
        std::cout << "Coordinate is already 3D: " << coords << std::endl;
        return coords;
    }
    pybind11::array_t<double> arr = coords.as2Dxy().asNumpyCartesian();
    auto r = arr.unchecked<2>();
    cv::Mat pt(1, 2, CV_64F);
    pt.at<double>(0, 0) = r(0, 0);
    pt.at<double>(0, 1) = r(0, 1);
    std::vector<cv::Point2f> pts;
    pts.emplace_back(pt.at<double>(0, 0), pt.at<double>(0, 1));
    std::vector<cv::Point2f> undistorted;
    cv::undistortPoints(pts, undistorted, intrinsics_, distortion_, cv::noArray(), intrinsics_);
    Point result(undistorted[0].x, undistorted[0].y);
    if (!std::isnan(distance)) {
        if (std::isnan(distance)) {
            throw std::runtime_error("Invalid distance");
        }
        result = Point(result.x() * distance, result.y() * distance, distance);
    }
    if (std::isnan(result.x()) || std::isnan(result.y())) {
        throw std::runtime_error("Invalid Point");
    }
    return result;
}


} // namespace tracking
} // namespace rv