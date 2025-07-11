#pragma once
#include <vector>
#include <stdexcept>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/calib3d.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/videoio.hpp>
#include <rv/tracking/point.h>
#include <rv/tracking/rectangle.h>

namespace rv {
namespace tracking {

class CameraIntrinsics {
public:
    static constexpr size_t DISTORTION_SIZE = 14;
    CameraIntrinsics(const std::vector<double>& intrinsics,
                     const std::vector<double>& distortion = std::vector<double>(DISTORTION_SIZE, 0.0),
                     const std::vector<int>& resolution = {});
    cv::Mat unwarp(const cv::Mat& image);
    cv::Mat pinholeUndistort(const cv::Mat& image);
    const cv::Mat& getIntrinsics() const { return intrinsics_; }
    const std::vector<double>& getDistortion() const { return distortion_; }
    const std::vector<int>& getResolution() const { return resolution_; }
    Point infer3DCoordsFrom2DDetection(const Point& coords, double distance = std::numeric_limits<double>::quiet_NaN());


private:
    cv::Mat intrinsics_;
    std::vector<double> distortion_;
    std::vector<int> resolution_;
    cv::Mat map1_;
    cv::Mat map2_;
    std::vector<int> crop_;
    cv::Mat undistort_intrinsics_;
    cv::Mat unwarp_intrinsics_;

    void setDistortion(const std::vector<double>& distortion);
    cv::Mat computeIntrinsicsFromFoV(const std::vector<int>& resolution, const std::vector<double>& fov);
    void createUndistortIntrinsics(const std::vector<int>& resolution);
};

} // namespace tracking
} // namespace rv
