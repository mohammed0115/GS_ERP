"""Inventory-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class WarehouseNotFoundError(NotFoundError):
    default_code = "warehouse_not_found"
    default_message = "Warehouse not found."


class InsufficientStockError(PreconditionFailedError):
    default_code = "insufficient_stock"
    default_message = "Stock on hand is insufficient for this operation."


class InvalidMovementError(ValidationError):
    default_code = "invalid_movement"
    default_message = "Stock movement is invalid."


class DuplicateMovementRefError(ConflictError):
    default_code = "duplicate_movement_ref"
    default_message = "A movement with this reference already exists."


class StockCountAlreadyFinalizedError(ConflictError):
    default_code = "stock_count_finalized"
    default_message = "Stock count is already finalized."


class NonStockableProductError(ValidationError):
    default_code = "non_stockable_product"
    default_message = "Cannot record stock movement for a non-stockable product (service, digital, or combo)."


# -- Adjustment -----------------------------------------------------------
class AdjustmentAlreadyPostedError(ConflictError):
    default_code = "adjustment_already_posted"
    default_message = "This adjustment has already been posted."


class EmptyAdjustmentError(ValidationError):
    default_code = "empty_adjustment"
    default_message = "An adjustment must have at least one line."


class InvalidAdjustmentLineError(ValidationError):
    default_code = "invalid_adjustment_line"
    default_message = "Adjustment line is invalid."


# -- Transfer -------------------------------------------------------------
class TransferAlreadyPostedError(ConflictError):
    default_code = "transfer_already_posted"
    default_message = "This transfer has already been posted."


class EmptyTransferError(ValidationError):
    default_code = "empty_transfer"
    default_message = "A transfer must have at least one line."


class InvalidTransferError(ValidationError):
    default_code = "invalid_transfer"
    default_message = "Transfer is invalid."


# -- Count ----------------------------------------------------------------
class EmptyStockCountError(ValidationError):
    default_code = "empty_stock_count"
    default_message = "A stock count must have at least one line."


class InvalidStockCountLineError(ValidationError):
    default_code = "invalid_stock_count_line"
    default_message = "Stock-count line is invalid."
