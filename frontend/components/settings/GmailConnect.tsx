'use client';

import { useState, useEffect } from 'react';
import { emailApi, EmailStatusResponse } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, Mail, Loader2, AlertCircle } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

export default function GmailConnect() {
  const [status, setStatus] = useState<EmailStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const data = await emailApi.getStatus();
      setStatus(data);
    } catch (error: any) {
      toast({
        title: 'Failed to load Gmail status',
        description: error.message || 'Could not check Gmail connection status',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    if (!status?.oauth_available) {
      toast({
        title: 'OAuth not configured',
        description: 'GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in the backend',
        variant: 'destructive',
      });
      return;
    }

    try {
      setConnecting(true);
      // Get redirect URI (callback page)
      const redirectUri = `${window.location.origin}/oauth/callback`;

      const response = await emailApi.getOAuthUrl(redirectUri);

      // Redirect to Google OAuth
      window.location.href = response.auth_url;
    } catch (error: any) {
      setConnecting(false);
      toast({
        title: 'Failed to start OAuth flow',
        description: error.response?.data?.detail || error.message || 'Could not initiate Gmail connection',
        variant: 'destructive',
      });
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Gmail Connection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Gmail Connection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground">
            Failed to load Gmail status
          </div>
        </CardContent>
      </Card>
    );
  }

  const isConnected = status.gmail_service_initialized && status.credentials_loaded;
  const hasOAuth = status.oauth_available;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="h-5 w-5" />
          Gmail Connection
        </CardTitle>
        <CardDescription>
          Connect your Gmail account to enable email sending for document escalations
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Badge */}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Badge variant="default" className="bg-green-600">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Connected
              </Badge>
              <span className="text-sm text-muted-foreground">
                Gmail is configured and ready to send emails
              </span>
            </>
          ) : (
            <>
              <Badge variant="destructive">
                <XCircle className="h-3 w-3 mr-1" />
                Not Connected
              </Badge>
              <span className="text-sm text-muted-foreground">
                Gmail is not configured
              </span>
            </>
          )}
        </div>

        {/* Error Message */}
        {status.error && (
          <div className="rounded-lg bg-destructive/10 p-3 border border-destructive/20">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-destructive">Error</p>
                <p className="text-xs text-destructive/80 mt-1">{status.error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Connection Details */}
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Sender Email:</span>
            <span className="font-medium">
              {status.gmail_sender_email !== 'not configured'
                ? status.gmail_sender_email
                : 'Not set'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Credentials:</span>
            <span className="font-medium">
              {status.credentials_loaded ? 'Loaded' : 'Not loaded'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">OAuth Available:</span>
            <span className="font-medium">
              {hasOAuth ? 'Yes' : 'No'}
            </span>
          </div>
        </div>

        {/* Connect Button */}
        {!isConnected && hasOAuth && (
          <Button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full"
          >
            {connecting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                <Mail className="h-4 w-4 mr-2" />
                Connect Gmail
              </>
            )}
          </Button>
        )}

        {!hasOAuth && (
          <div className="rounded-lg bg-muted p-3">
            <p className="text-xs text-muted-foreground">
              To enable OAuth connection, set <code className="bg-background px-1 py-0.5 rounded">GMAIL_CLIENT_ID</code> and{' '}
              <code className="bg-background px-1 py-0.5 rounded">GMAIL_CLIENT_SECRET</code> in your backend environment variables.
            </p>
          </div>
        )}

        {/* Instructions */}
        {status.troubleshooting.needs_refresh_token && !hasOAuth && (
          <div className="rounded-lg bg-yellow-50 dark:bg-yellow-900/20 p-3 border border-yellow-200 dark:border-yellow-800">
            <p className="text-xs font-medium text-yellow-800 dark:text-yellow-200 mb-1">
              Manual Setup:
            </p>
            <p className="text-xs text-yellow-700 dark:text-yellow-300">
              {status.troubleshooting.instructions}
            </p>
          </div>
        )}

        {/* Refresh Button */}
        <Button
          onClick={loadStatus}
          variant="outline"
          size="sm"
          className="w-full"
        >
          Refresh Status
        </Button>
      </CardContent>
    </Card>
  );
}
