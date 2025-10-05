import React, { useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Chip,
  Grid,
  Card,
  CardContent,
  Button,
  Divider,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  Table,
  TableBody,
  TableRow,
  TableCell,
  TableHead
} from '@mui/material';
import {
  Schedule as ScheduleIcon,
  LocationOn as LocationOnIcon,
  AttachMoney as AttachMoneyIcon,
  Phone as PhoneIcon,
  Star as StarIcon,
  Warning as WarningIcon,
  DirectionsWalk as DirectionsWalkIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Timeline as TimelineIcon
} from '@mui/icons-material';

const BookingResult = ({ result, onBookSlot, onReset, user }) => {
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [isBooking, setIsBooking] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const formatDateTime = (dateTimeStr) => {
    if (!dateTimeStr) {
      return {
        dateLabel: 'Unknown date',
        timeLabel: '',
        fullLabel: 'Unknown date'
      };
    }

    try {
      const date = new Date(dateTimeStr);

      if (Number.isNaN(date.getTime())) {
        throw new Error('Invalid date');
      }

      const timeZone = 'Asia/Dubai';
      const dateFormatter = new Intl.DateTimeFormat('en-US', {
        weekday: 'long',
        month: 'short',
        day: 'numeric',
        timeZone
      });
      const timeFormatter = new Intl.DateTimeFormat('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
        timeZone
      });

      const dateLabel = dateFormatter.format(date);
      const timeLabel = timeFormatter.format(date);

      return {
        dateLabel,
        timeLabel,
        fullLabel: `${dateLabel} at ${timeLabel} (GST)`
      };
    } catch (error) {
      console.error('Error formatting date:', error);
      return {
        dateLabel: 'Invalid date',
        timeLabel: '',
        fullLabel: dateTimeStr
      };
    }
  };

  const handleSlotClick = (slot) => {
    // Only allow selection if not booked
    if (!slot.isBooked) {
      if (!user || !user.uid) {
        setFeedback({ severity: 'warning', message: 'Sign in to confirm a booking.' });
        return;
      }

      setFeedback(null);
      setSelectedSlot(slot);
      setConfirmDialogOpen(true);
    }
  };

  const formatCurrency = (value) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return `AED ${value.toFixed(2)}`;
    }
    return 'AED 0.00';
  };

  const getDistanceLabel = (provider) => {
    if (!provider) return null;
    if (provider.distance) {
      return provider.distance;
    }
    if (typeof provider.distance_km === 'number') {
      if (provider.distance_km < 1) {
        return `${Math.round(provider.distance_km * 1000)} m`;
      }
      return `${provider.distance_km.toFixed(1)} km`;
    }
    return null;
  };

  const getStepMeta = (status = '') => {
    const normalized = status.toLowerCase();
    if (normalized === 'success') {
      return { color: 'success.main', Icon: CheckCircleIcon, label: 'Success' };
    }
    if (normalized === 'error' || normalized === 'failed' || normalized === 'failure') {
      return { color: 'error.main', Icon: ErrorIcon, label: 'Error' };
    }
    if (normalized === 'running' || normalized === 'in-progress') {
      return { color: 'info.main', Icon: TimelineIcon, label: 'Running' };
    }
    return { color: 'text.secondary', Icon: TimelineIcon, label: status || 'Info' };
  };

  const handleConfirmBooking = async () => {
    if (!selectedSlot) return;
    if (!user || !user.uid) {
      setFeedback({ severity: 'warning', message: 'You need to sign in before confirming a booking.' });
      setConfirmDialogOpen(false);
      return;
    }

    setIsBooking(true);
    setConfirmDialogOpen(false);
    setFeedback(null);

    const toIsoIfPossible = (value) => {
      if (!value) return value;
      try {
        const date = new Date(value);
        if (!Number.isNaN(date.getTime())) {
          return date.toISOString();
        }
      } catch (error) {
        // Ignore parsing issues and fall back to original value
      }
      return value;
    };

    const normalizedSelectedSlot = {
      ...selectedSlot,
      start: toIsoIfPossible(selectedSlot.start),
      end: toIsoIfPossible(selectedSlot.end)
    };

    try {
      const response = await fetch('/book-confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          uid: user.uid,
          user_name: user.displayName || user.email || '',
          user_email: user.email || '',
          service_name: serviceName,
          service: serviceName,
          provider,
          pricing,
          selected_slot: normalizedSelectedSlot,
          location: result?.proposal?.location,
          query: result?.query || ''
        })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to confirm booking');
      }

      setFeedback({
        severity: 'success',
        message: data.message || 'Booking confirmed successfully!'
      });

      if (typeof onBookSlot === 'function') {
        onBookSlot({
          success: true,
          bookingId: data.booking_id,
          selectedSlot: normalizedSelectedSlot,
          provider,
          serviceName,
          pricing
        });
      }
    } catch (error) {
      setFeedback({
        severity: 'error',
        message: error?.message || 'Unable to confirm booking. Please try again.'
      });
    } finally {
      setIsBooking(false);
      setSelectedSlot(null);
    }
  };

  const handleCancelBooking = () => {
    setConfirmDialogOpen(false);
    setSelectedSlot(null);
  };

  // Handle error cases
  if (!result) {
    return null;
  }

  // Show error message if backend returned an error
  if (result.error) {
    const errorMessage = typeof result.error === 'string' ? result.error : 'Something went wrong';
    const isContextError = errorMessage.toLowerCase().includes('unable to understand');

    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Alert severity="error" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            ⚠️ Booking Error
          </Typography>
          <Typography variant="body2" sx={{ mb: isContextError ? 2 : 0 }}>
            {isContextError
              ? 'I couldn’t map that request to a Dubai appointment yet.'
              : errorMessage}
          </Typography>
          {isContextError && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                Try asking with:
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • A specific beauty or wellness service (e.g., massage, haircut)<br />
                • The Dubai area or neighborhood you prefer<br />
                • A day or time window (morning, afternoon, evening)
              </Typography>
            </Box>
          )}
          <Button
            variant="outlined"
            size="small"
            onClick={onReset}
            sx={{ mt: 2 }}
          >
            Try Again
          </Button>
        </Alert>
      </Container>
    );
  }

  // Show message if no proposal (no providers found)
  if (!result.proposal) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Alert severity="warning" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            😔 No Available Providers
          </Typography>
          <Typography variant="body2">
            We couldn't find any providers offering this service at the moment. 
            Please try a different service, time, or location.
          </Typography>
          <Button
            variant="outlined"
            size="small"
            onClick={onReset}
            sx={{ mt: 2 }}
          >
            Search Again
          </Button>
        </Alert>
      </Container>
    );
  }

  // Show message if no slots available
  if (!result.proposal.available_slots || result.proposal.available_slots.length === 0) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            📅 No Available Slots
          </Typography>
          <Typography variant="body2">
            Sorry, there are no available time slots matching your preferences at{' '}
            <strong>{result.proposal.provider?.name}</strong>.
            <br /><br />
            Please try:
            <ul style={{ marginTop: 8, marginBottom: 8 }}>
              <li>A different date or time</li>
              <li>A different location</li>
              <li>Removing specific time preferences (morning/afternoon/evening)</li>
            </ul>
          </Typography>
          <Button
            variant="outlined"
            size="small"
            onClick={onReset}
            sx={{ mt: 2 }}
          >
            Search Again
          </Button>
        </Alert>
      </Container>
    );
  }

  const { proposal, steps = [] } = result;
  const provider = proposal.provider || {};
  const providerName = provider.name || 'Selected Provider';
  const pricing = proposal.pricing || {};
  const availableSlots = proposal.available_slots || [];
  const serviceName = proposal.service || pricing.service_name || 'Selected Service';
  const userLocation = proposal.location;
  const distanceLabel = getDistanceLabel(provider);
  const rawAddOns = Array.isArray(pricing.add_ons)
    ? pricing.add_ons
    : Array.isArray(pricing.addOns)
    ? pricing.addOns
    : [];
  const normalizedAddOns = rawAddOns.map((addon, index) => ({
    name: addon?.name || addon?.title || `Add-on ${index + 1}`,
    price: typeof addon?.price === 'number' ? addon.price : addon?.cost || 0
  }));
  const addOnTotal = typeof pricing.add_on_total === 'number'
    ? pricing.add_on_total
    : typeof pricing.addOnTotal === 'number'
    ? pricing.addOnTotal
    : normalizedAddOns.reduce((sum, addon) => sum + (addon.price || 0), 0);
  const basePriceValue = typeof pricing.base_price === 'number'
    ? pricing.base_price
    : Math.max(0, (typeof pricing.subtotal === 'number' ? pricing.subtotal : 0) - addOnTotal);
  const subtotalValue = typeof pricing.subtotal === 'number'
    ? pricing.subtotal
    : basePriceValue + addOnTotal;
  const totalPriceValue = typeof pricing.total_price === 'number'
    ? pricing.total_price
    : (subtotalValue + (typeof pricing.tax === 'number' ? pricing.tax : subtotalValue * 0.05));
  const taxValue = typeof pricing.tax === 'number'
    ? pricing.tax
    : Math.max(0, totalPriceValue - subtotalValue);
  const providerTier = pricing.provider_tier;
  const estimatedDuration = pricing.duration || availableSlots[0]?.duration || 60;
  const hasBookedSlots = availableSlots.some((slot) => slot.isBooked);

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: { xs: 3, md: 4 }, mt: 3 }}>
        <Stack spacing={4}>
          {feedback?.message && (
            <Alert
              severity={feedback.severity || 'info'}
              onClose={() => setFeedback(null)}
            >
              {feedback.message}
            </Alert>
          )}

          <Box>
            <Typography variant="overline" color="primary" sx={{ letterSpacing: 1, fontWeight: 600 }}>
              Booking Proposal
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                fontFamily: '"Inter", "Segoe UI", "Roboto", "Helvetica", "Arial", sans-serif',
                letterSpacing: '-0.5px',
                color: '#0d532e',
                mb: 1
              }}
            >
              {serviceName}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              We found an excellent match for your request{userLocation ? ` near ${userLocation}` : ''} at{' '}
              <strong>{providerName}</strong>.
            </Typography>

            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 2 }}>
              <Chip
                icon={<ScheduleIcon />}
                label={serviceName}
                color="primary"
                variant="outlined"
                sx={{ mr: 1, mb: 1 }}
              />
              {userLocation && (
                <Chip
                  icon={<LocationOnIcon />}
                  label={`Preferred area: ${userLocation}`}
                  variant="outlined"
                  sx={{ mr: 1, mb: 1 }}
                />
              )}
              {distanceLabel && (
                <Chip
                  icon={<DirectionsWalkIcon />}
                  label={`${distanceLabel}${userLocation ? ` from ${userLocation}` : ''}`}
                  variant="outlined"
                  sx={{ mr: 1, mb: 1 }}
                />
              )}
              {providerTier && (
                <Chip
                  label={`${providerTier} provider`}
                  color="secondary"
                  variant="outlined"
                  sx={{ mr: 1, mb: 1 }}
                />
              )}
            </Stack>
          </Box>

          <Grid container spacing={3}>
            <Grid item xs={12} md={7}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Provider details
                  </Typography>
                  <Stack spacing={1.5}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      {providerName}
                    </Typography>
                    {provider.location && (
                      <Stack direction="row" spacing={1} alignItems="center">
                        <LocationOnIcon fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary">
                          {provider.location}
                        </Typography>
                      </Stack>
                    )}
                    {distanceLabel && (
                      <Stack direction="row" spacing={1} alignItems="center">
                        <DirectionsWalkIcon fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary">
                          {distanceLabel}{userLocation ? ` from ${userLocation}` : ''}
                        </Typography>
                      </Stack>
                    )}
                    {provider.phone && (
                      <Stack direction="row" spacing={1} alignItems="center">
                        <PhoneIcon fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary">
                          {provider.phone}
                        </Typography>
                      </Stack>
                    )}
                    {provider.rating && (
                      <Stack direction="row" spacing={1} alignItems="center">
                        <StarIcon fontSize="small" sx={{ color: '#FFD700' }} />
                        <Typography variant="body2" color="text.secondary">
                          {provider.rating} / 5.0 rating
                        </Typography>
                      </Stack>
                    )}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={5}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Service overview
                  </Typography>
                  <Stack spacing={1.5}>
                    <Typography variant="body2">
                      <strong>Service:</strong> {serviceName}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Estimated duration:</strong> {estimatedDuration} minutes
                    </Typography>
                    <Typography variant="body2">
                      <strong>Slots returned:</strong> {availableSlots.length}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Select a preferred time slot below to confirm your booking.
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card>
            <CardContent>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <AttachMoneyIcon color="primary" />
                <Typography variant="h6">Pricing breakdown</Typography>
              </Stack>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell component="th">Item</TableCell>
                    <TableCell align="right">Amount</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>Base service price</TableCell>
                    <TableCell align="right">{formatCurrency(basePriceValue)}</TableCell>
                  </TableRow>
                  {normalizedAddOns.length > 0 && (
                    <TableRow>
                      <TableCell colSpan={2} sx={{ pt: 2, pb: 0, fontWeight: 600 }}>
                        Applied add-ons
                      </TableCell>
                    </TableRow>
                  )}
                  {normalizedAddOns.map((addon, index) => (
                    <TableRow key={`${addon.name}-${index}`}>
                      <TableCell sx={{ pl: 4 }}>{addon.name}</TableCell>
                      <TableCell align="right">{formatCurrency(addon.price)}</TableCell>
                    </TableRow>
                  ))}
                  {normalizedAddOns.length > 0 && (
                    <TableRow>
                      <TableCell sx={{ fontStyle: 'italic' }}>Add-on total</TableCell>
                      <TableCell align="right">{formatCurrency(addOnTotal)}</TableCell>
                    </TableRow>
                  )}
                  <TableRow>
                    <TableCell>Subtotal</TableCell>
                    <TableCell align="right">{formatCurrency(subtotalValue)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Tax (5%)</TableCell>
                    <TableCell align="right">{formatCurrency(taxValue)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Total due</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: 'primary.main' }}>
                      {formatCurrency(totalPriceValue)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              {providerTier && (
                <Chip
                  label={`${providerTier} provider`}
                  size="small"
                  color="primary"
                  variant="outlined"
                  sx={{ mt: 2 }}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <ScheduleIcon color="primary" />
                <Typography variant="h6">Available time slots</Typography>
              </Stack>

              {!user && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Sign in to confirm your booking. You can preview slots below, but confirming requires an account.
                </Alert>
              )}

              {hasBookedSlots && (
                <Alert severity="info" icon={<WarningIcon />} sx={{ mb: 2 }}>
                  Slots marked in grey are already booked and cannot be selected.
                </Alert>
              )}

              <Grid container spacing={1.5}>
                {availableSlots.map((slot) => {
                  const slotLabels = formatDateTime(slot.start);
                  const isBooked = slot.isBooked === true;
                  const isSelected = Boolean(
                    selectedSlot &&
                    (selectedSlot.slot_id ? selectedSlot.slot_id === slot.slot_id : selectedSlot === slot)
                  );

                  return (
                    <Grid item xs={12} sm={6} md={4} key={slot.slot_id || slot.start}>
                      <Chip
                        label={
                          <Box sx={{ textAlign: 'left', lineHeight: 1.2 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                              {slotLabels.dateLabel}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {slotLabels.timeLabel}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {slot.duration || 60} mins • Gulf Standard Time{isBooked ? ' • BOOKED' : ''}
                            </Typography>
                          </Box>
                        }
                        onClick={() => handleSlotClick(slot)}
                        variant={isSelected && !isBooked ? 'filled' : 'outlined'}
                        color={isBooked ? 'default' : isSelected ? 'primary' : 'default'}
                        clickable={!isBooked && Boolean(user)}
                        disabled={isBooked || !user}
                        sx={{
                          width: '100%',
                          height: 'auto',
                          py: 1.2,
                          borderRadius: 2,
                          borderColor: isBooked ? '#bdbdbd' : isSelected ? 'primary.main' : undefined,
                          backgroundColor: isBooked ? '#e0e0e0' : undefined,
                          color: isBooked ? '#757575' : undefined,
                          boxShadow: isSelected ? '0 6px 16px rgba(25, 118, 210, 0.2)' : 'none'
                        }}
                      />
                    </Grid>
                  );
                })}
              </Grid>

              {selectedSlot && !selectedSlot.isBooked && (
                <Alert severity="success" sx={{ mt: 3 }}>
                  <Typography variant="body2">
                    <strong>Selected slot:</strong> {formatDateTime(selectedSlot.start).fullLabel}
                  </Typography>
                </Alert>
              )}
            </CardContent>
          </Card>

          <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 2 }}>
            <Button
              variant="outlined"
              size="large"
              onClick={onReset}
              disabled={isBooking}
              sx={{ py: 1.4 }}
            >
              Search Again
            </Button>
          </Box>

          {Array.isArray(steps) && steps.length > 0 && (
            <Card sx={{ backgroundColor: '#f8f9fa' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  AI process steps
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  A quick look at how the agent prepared this recommendation.
                </Typography>
                <Stack spacing={2}>
                  {steps.map((step, index) => {
                    const { color, Icon, label } = getStepMeta(step.status);
                    return (
                      <Box
                        key={`${step.tool}-${index}`}
                        sx={{
                          backgroundColor: 'white',
                          borderRadius: 2,
                          border: '1px solid',
                          borderColor: 'rgba(13, 83, 46, 0.1)',
                          p: 2
                        }}
                      >
                        <Stack direction="row" spacing={2} alignItems="flex-start">
                          <Icon fontSize="small" sx={{ mt: 0.5, color }} />
                          <Box sx={{ flex: 1 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                Step {index + 1}: {step.tool}
                              </Typography>
                              <Chip
                                label={label}
                                size="small"
                                sx={{ backgroundColor: `${color}1A`, color, textTransform: 'capitalize' }}
                              />
                            </Stack>
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                              <strong>Action:</strong> {step.action}
                            </Typography>
                            {step.input && (
                              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                <strong>Input:</strong> {step.input}
                              </Typography>
                            )}
                            {step.output && (
                              <Typography variant="body2" sx={{ mt: 0.5 }}>
                                <strong>Result:</strong> {step.output}
                              </Typography>
                            )}
                          </Box>
                        </Stack>
                      </Box>
                    );
                  })}
                </Stack>
              </CardContent>
            </Card>
          )}
        </Stack>
      </Paper>

      {/* Confirmation Dialog */}
      <Dialog 
        open={confirmDialogOpen} 
        onClose={handleCancelBooking}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 3,
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)'
          }
        }}
      >
        <DialogTitle
          sx={{
            fontFamily: '"Inter", "Segoe UI", "Roboto", sans-serif',
            fontWeight: 600,
            fontSize: '1.5rem',
            color: '#1a1a1a',
            pt: 3,
            pb: 2
          }}
        >
          Confirm your booking
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          {selectedSlot && (
            <Stack spacing={2}>
              <Box
                sx={{
                  bgcolor: '#f8f9fa',
                  p: 3,
                  borderRadius: 2,
                  border: '1px solid #e0e0e0'
                }}
              >
                {(() => {
                  const slotLabels = formatDateTime(selectedSlot.start);
                  return (
                    <Stack spacing={1.2}>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {serviceName} at {providerName}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {slotLabels.fullLabel} • {selectedSlot.duration || 60} minutes
                      </Typography>
                      {distanceLabel && (
                        <Typography variant="body2" color="text.secondary">
                          Distance: {distanceLabel}{userLocation ? ` from ${userLocation}` : ''}
                        </Typography>
                      )}
                      {normalizedAddOns.length > 0 ? (
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                            Included add-ons
                          </Typography>
                          {normalizedAddOns.map((addon, index) => (
                            <Typography key={`${addon.name}-${index}`} variant="body2" color="text.secondary">
                              • {addon.name} ({formatCurrency(addon.price)})
                            </Typography>
                          ))}
                        </Box>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No add-ons selected
                        </Typography>
                      )}
                    </Stack>
                  );
                })()}
              </Box>

              <Box
                sx={{
                  borderRadius: 2,
                  border: '1px solid #e0e0e0',
                  p: 3,
                  bgcolor: 'white'
                }}
              >
                <Stack spacing={1.2}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">
                      Base price
                    </Typography>
                    <Typography variant="body2">{formatCurrency(basePriceValue)}</Typography>
                  </Stack>
                  {normalizedAddOns.length > 0 && (
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">
                        Add-ons
                      </Typography>
                      <Typography variant="body2">{formatCurrency(addOnTotal)}</Typography>
                    </Stack>
                  )}
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">
                      Tax (5%)
                    </Typography>
                    <Typography variant="body2">{formatCurrency(taxValue)}</Typography>
                  </Stack>
                  <Divider sx={{ my: 1.5 }} />
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                      Total due today
                    </Typography>
                    <Typography variant="h6" color="primary">
                      {formatCurrency(totalPriceValue)}
                    </Typography>
                  </Stack>
                </Stack>
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2.5 }}>
          <Button 
            onClick={handleCancelBooking} 
            disabled={isBooking}
            sx={{ 
              fontFamily: '"Inter", "Segoe UI", sans-serif',
              fontWeight: 500,
              fontSize: '0.95rem',
              textTransform: 'none',
              px: 3,
              py: 1
            }}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleConfirmBooking} 
            variant="contained" 
            disabled={isBooking}
            autoFocus
            sx={{ 
              fontFamily: '"Inter", "Segoe UI", sans-serif',
              fontWeight: 600,
              fontSize: '0.95rem',
              textTransform: 'none',
              px: 3,
              py: 1,
              borderRadius: 2,
              boxShadow: '0 4px 12px rgba(25, 118, 210, 0.3)',
              '&:hover': {
                boxShadow: '0 6px 16px rgba(25, 118, 210, 0.4)'
              }
            }}
          >
            {isBooking ? '⏳ Booking...' : ' Confirm Booking'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default BookingResult;