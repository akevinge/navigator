/*
 * Package:   voltron_can
 * Filename:  CanFrame.cpp
 * Author:    Joshua Williams
 * Email:     joshmackwilliams@protonmail.com
 * Copyright: 2021, Voltron UTD
 * License:   MIT License
 */

// Class to represent a CAN frame

#include <linux/can.h>

#include "voltron_can/CanFrame.hpp"

using namespace Voltron::Can;

CanFrame::CanFrame(CanFrame::identifier_t identifier, CanFrame::data_t data) {
  this->identifier = identifier;
  this->data = data;
}

CanFrame::CanFrame(const struct can_frame & frame_struct) {
  this->identifier = (identifier_t) frame_struct.can_id;
  this->data = *((data_t *) frame_struct.data);
}

CanFrame::~CanFrame() {}

CanFrame::identifier_t CanFrame::get_identifier() const {
  return this->identifier;
}

CanFrame::data_t CanFrame::get_data() const {
  return this->data;
}

std::unique_ptr<struct can_frame> CanFrame::to_system_frame() const {
  auto system_frame = std::make_unique<struct can_frame>();
  system_frame->can_id = this->identifier;
  (*(CanFrame::data_t *) system_frame->data) = this->data;
  system_frame->can_dlc = 8;
  return system_frame;
}
