module.exports = async function handler(req, res) {
  const ALB = 'http://groundcheck-alb-2146650864.us-east-1.elb.amazonaws.com';

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
    const chunks = [];
    await new Promise((resolve, reject) => {
      req.on('data', (c) => chunks.push(c));
      req.on('end', resolve);
      req.on('error', reject);
    });
    fetchOpts.body = Buffer.concat(chunks);
  }

  const upstream = await fetch(targetUrl, fetchOpts);

  res.status(upstream.status);
  upstream.headers.forEach((v, k) => {
    if (!['transfer-encoding', 'connection'].includes(k)) res.setHeader(k, v);
  });

  res.send(Buffer.from(await upstream.arrayBuffer()));
};

module.exports.config = { api: { bodyParser: false } };
