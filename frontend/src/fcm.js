// Firebase configuration for FCM - Updated to use existing app
import { getApps, getApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

// FCM Service for handling push notifications
export class FCMService {
  constructor() {
    this.vapidKey = "your gen key pair"; 
    this.messaging = null;
    this.serviceWorkerRegistration = null;
    this.serviceWorkerPath = '/firebase-messaging-sw.js';
    this._initializeMessaging();
  }

  _initializeMessaging() {
    try {
      const apps = getApps();
      if (apps.length > 0) {
        const app = getApp();
        this.messaging = getMessaging(app);
      } else {
        console.error('No Firebase app found');
      }
    } catch (error) {
      console.error('Error initializing Firebase messaging:', error);
    }
  }

  // Request notification permission and get FCM token
  async requestPermission() {
    if (!this.messaging) {
      return {
        success: false,
        error: 'Firebase messaging not initialized'
      };
    }

    try {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        if (!('serviceWorker' in navigator)) {
          return {
            success: false,
            error: 'Service workers are not supported in this browser'
          };
        }

        // Ensure we have a registered service worker
        try {
          let registration = this.serviceWorkerRegistration;

          if (!registration) {
            registration = await navigator.serviceWorker.getRegistration(this.serviceWorkerPath);
          }

          if (!registration) {
            registration = await navigator.serviceWorker.register(this.serviceWorkerPath, {
              scope: '/'
            });
          }

          const readyRegistration = await navigator.serviceWorker.ready.catch(() => null);
          if (readyRegistration) {
            registration = readyRegistration;
          }

          registration = await this._ensureServiceWorkerActive(registration);

          this.serviceWorkerRegistration = registration;
        } catch (swError) {
          console.error('Service worker registration error:', swError);
          return {
            success: false,
            error: `Service worker error: ${swError.message}`
          };
        }
        
        try {
          const registration = this.serviceWorkerRegistration || (await navigator.serviceWorker.ready);
          const token = await this._getTokenWithRegistration(registration);
          
          if (token) {
            localStorage.setItem('fcm_token', token);
            return {
              success: true,
              token: token,
              message: 'Push notifications enabled!'
            };
          } else {
            return {
              success: false,
              error: 'Failed to get FCM token'
            };
          }
        } catch (tokenError) {
          const message = tokenError?.message || String(tokenError);
          console.error('FCM token error:', message);
          const lower = message.toLowerCase();
          return {
            success: false,
            error: lower.includes('push service error')
              ? 'Push notifications are unavailable right now (push service error).'
              : message,
            code: lower.includes('push service error') ? 'push-service-error' : undefined
          };
        }
      } else {
        return {
          success: false,
          error: 'Notification permission denied'
        };
      }
    } catch (error) {
      console.error('Error requesting permission:', error.message);
      return {
        success: false,
        error: error.message
      };
    }
  }

  async _ensureServiceWorkerActive(registration) {
    if (!registration) {
      throw new Error('Service worker registration not available');
    }

    if (registration.active) {
      return registration;
    }

    const ready = await navigator.serviceWorker.ready.catch(() => null);
    if (ready?.active) {
      return ready;
    }

    const sw = registration.installing || registration.waiting;
    if (sw) {
      await new Promise((resolve, reject) => {
        const onStateChange = () => {
          if (sw.state === 'activated') {
            sw.removeEventListener('statechange', onStateChange);
            resolve();
          } else if (sw.state === 'redundant') {
            sw.removeEventListener('statechange', onStateChange);
            reject(new Error('Service worker became redundant before activation'));
          }
        };
        sw.addEventListener('statechange', onStateChange);
      });
    }

    if (registration.active) {
      return registration;
    }

    throw new Error('Service worker not activated yet');
  }

  async _getTokenWithRegistration(registration) {
    if (!registration) {
      throw new Error('Service worker registration not available');
    }

    if (!('pushManager' in registration) || typeof registration.pushManager?.getSubscription !== 'function') {
      throw new Error('Push notifications are not supported in this browser environment');
    }

    try {
      return await getToken(this.messaging, {
        vapidKey: this.vapidKey,
        serviceWorkerRegistration: registration
      });
    } catch (tokenError) {
      const message = tokenError && tokenError.message ? tokenError.message : String(tokenError);
      console.error('FCM token error:', message);

      // Handle stale push subscriptions (e.g., when VAPID key changes)
      if (registration && registration.pushManager) {
        try {
          const existingSubscription = await registration.pushManager.getSubscription();
          if (existingSubscription) {
            await existingSubscription.unsubscribe();
            return await getToken(this.messaging, {
              vapidKey: this.vapidKey,
              serviceWorkerRegistration: registration
            });
          }
        } catch (subscriptionError) {
          console.warn('Unable to reset push subscription:', subscriptionError);
        }
      }

      if (typeof navigator !== 'undefined' && navigator.serviceWorker && message.toLowerCase().includes('push service error')) {
        try {
          if (registration && typeof registration.unregister === 'function') {
            await registration.unregister();
          }

          const freshRegistration = await navigator.serviceWorker.register(this.serviceWorkerPath, {
            scope: '/'
          });

          this.serviceWorkerRegistration = freshRegistration;

          return await getToken(this.messaging, {
            vapidKey: this.vapidKey,
            serviceWorkerRegistration: freshRegistration
          });
        } catch (retryError) {
          console.warn('FCM retry after push service error failed:', retryError);
        }
      }

      throw tokenError;
    }
  }

  // Listen for foreground messages
  onMessage(callback) {
    if (!this.messaging) return;

    onMessage(this.messaging, (payload) => {
      if (callback) {
        callback(payload);
      }
      
      // Show browser notification if permission granted
      if (Notification.permission === 'granted') {
        const notification = payload.notification;
        new Notification(notification.title, {
          body: notification.body,
          icon: notification.icon || '/favicon.svg',
          badge: notification.badge || '/favicon.svg',
          tag: notification.tag,
          data: payload.data
        });
      }
    });
  }

  // Get current FCM token
  getCurrentToken() {
    return localStorage.getItem('fcm_token');
  }

  // Check if notifications are supported and enabled
  isSupported() {
    return 'Notification' in window && 'serviceWorker' in navigator && !!this.messaging;
  }

  // Show notification status
  getNotificationStatus() {
    if (!this.isSupported()) {
      return { status: 'unsupported', message: 'Push notifications not supported' };
    }
    
    if (Notification.permission === 'granted') {
      return { status: 'enabled', message: 'Push notifications enabled' };
    } else if (Notification.permission === 'denied') {
      return { status: 'denied', message: 'Push notifications blocked' };
    } else {
      return { status: 'default', message: 'Click to enable push notifications' };
    }
  }
}

export default FCMService;