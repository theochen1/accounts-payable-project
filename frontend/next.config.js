const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // Explicitly set the alias
    const alias = config.resolve.alias || {};
    alias['@'] = path.join(__dirname);
    config.resolve.alias = alias;
    
    return config;
  },
}

module.exports = nextConfig

