export const config = { api: { bodyParser: false } };

const ALB = 'http://groundcheck-alb-2146650864.us-east-1.elb.amazonaws.com';

function collectBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

export default async function handler(req, res) {
  const { path = [] } = req.query;
  const segments = Array.isArray(path) ? path : [path];
  const pathStr = segments.join('/');

  const reqUrl = new URL(req.url, 'http://placeholder');
  reqUrl.searchParams.delete('path');

  const targetUrl = `${ALB}/api/v1/${pathStr}${reqUrl.search}`;

  const headers = Object.fromEntries(
    Object.entries(req.headers).filter(([k]) => k.toLowerCase() !== 'host')
  );

  const fetchOpts = { method: req.method, headers };

  if (!['GET', 'HEAD', 'DELETE'].includes(req.method.toUpperCase())) {
    fetchOpts.body = await collectBody(req);
  }

  const upstream = await fetch(targetUrl, fetchOpts);

  res.status(upstream.status);
  upstream.headers.forEach((v, k) => {
    if (!['transfer-encoding', 'connection'].includes(k)) res.setHeader(k, v);
  });

  res.send(Buffer.from(await upstream.arrayBuffer()));
}
