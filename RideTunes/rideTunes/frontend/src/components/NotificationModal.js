import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, List, ListItem, ListItemText, ListItemSecondaryAction, Typography } from '@mui/material';
import { format } from 'date-fns'; // Import format from date-fns for date formatting

const NotificationModal = ({ isOpen, notifications, handleClose, handleAccept, handleDecline }) => {
  return (
    <Dialog open={isOpen} onClose={handleClose}>
      <DialogTitle>Notifications</DialogTitle>
      <DialogContent>
        <List>
          {notifications.map(notification => (
            <ListItem key={notification.id}>
              <ListItemText
                primary={notification.message}
                secondary={format(new Date(notification.timestamp), 'MM/dd/yyyy')} // Use format from date-fns
              />
              <ListItemSecondaryAction>
                <Button onClick={() => handleAccept(notification.id)}>Accept</Button>
                <Button onClick={() => handleDecline(notification.id)}>Decline</Button>
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default NotificationModal;
