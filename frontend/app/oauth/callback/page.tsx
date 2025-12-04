'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { emailApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Copy, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

export default function OAuthCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');

      if (errorParam) {
        setError(`OAuth error: ${errorParam}`);
        setStatus('error');
        return;
      }

      if (!code) {
        setError('No authorization code received from Google');
        setStatus('error');
        return;
      }

      try {
        // Get redirect URI (current page URL without query params)
        const redirectUri = `${window.location.origin}${window.location.pathname}`;

        const response = await emailApi.exchangeOAuthCode(code, state, redirectUri);
        setResult(response);
        setStatus('success');
      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Failed to exchange authorization code');
        setStatus('error');
      }
    };

    handleCallback();
  }, [searchParams]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: 'Copied to clipboard',
      description: 'Refresh token copied to clipboard',
    });
  };

  if (status === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              Completing Gmail Connection...
            </CardTitle>
            <CardDescription>Exchanging authorization code for tokens</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex h-screen items-center justify-center p-4">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <XCircle className="h-5 w-5" />
              Connection Failed
            </CardTitle>
            <CardDescription>Failed to complete Gmail OAuth connection</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-destructive/10 p-4">
              <p className="text-sm text-destructive">{error}</p>
            </div>
            <Button onClick={() => router.push('/')} variant="outline" className="w-full">
              Return to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-screen items-center justify-center p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-green-600">
            <CheckCircle2 className="h-5 w-5" />
            Gmail Connected Successfully!
          </CardTitle>
          <CardDescription>Your Gmail account has been authorized</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg bg-muted p-4 space-y-3">
            <div>
              <p className="text-sm font-medium mb-2">Next Steps:</p>
              <p className="text-sm text-muted-foreground">
                Copy the refresh token below and set it as the <code className="bg-background px-1 py-0.5 rounded">GMAIL_REFRESH_TOKEN</code> environment variable in your backend.
              </p>
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium">Refresh Token:</label>
              <div className="flex gap-2">
                <code className="flex-1 bg-background p-2 rounded text-xs break-all">
                  {result?.refresh_token}
                </code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(result?.refresh_token)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="rounded bg-yellow-50 dark:bg-yellow-900/20 p-3 border border-yellow-200 dark:border-yellow-800">
              <p className="text-xs font-medium text-yellow-800 dark:text-yellow-200 mb-1">
                Important:
              </p>
              <ul className="text-xs text-yellow-700 dark:text-yellow-300 space-y-1 list-disc list-inside">
                <li>Keep this refresh token secure and private</li>
                <li>Set it as an environment variable: <code>GMAIL_REFRESH_TOKEN=your_token_here</code></li>
                <li>Restart your backend server after setting the environment variable</li>
                <li>You also need to set <code>GMAIL_SENDER_EMAIL</code> to your Gmail address</li>
              </ul>
            </div>
          </div>

          <div className="flex gap-2">
            <Button onClick={() => router.push('/')} className="flex-1">
              Return to Dashboard
            </Button>
            <Button
              onClick={() => copyToClipboard(result?.refresh_token)}
              variant="outline"
            >
              Copy Token
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
