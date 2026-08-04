(function () {
  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function methodClass(method) {
    return String(method || "").toLowerCase();
  }

  function normalizeBaseUrl() {
    return window.location.origin || (window.location.protocol + "//" + window.location.host);
  }

  function buildParamInputs(operation, path, method, index) {
    var params = operation.parameters || [];
    if (!params.length) return "";

    var html = '<div class="parameters"><div class="section-title">Parameters</div>';
    html += '<table><thead><tr><th>Name</th><th>In</th><th>Required</th><th>Description</th><th>Value</th></tr></thead><tbody>';

    params.forEach(function (p, pIndex) {
      var key = 'op-' + index + '-param-' + pIndex;
      var required = p.required ? 'required' : 'optional';
      var placeholder = p.schema && p.schema.default !== undefined ? p.schema.default : '';
      html += '<tr>';
      html += '<td><code>' + escapeHtml(p.name) + '</code></td>';
      html += '<td>' + escapeHtml(p.in) + '</td>';
      html += '<td>' + escapeHtml(required) + '</td>';
      html += '<td>' + escapeHtml(p.description || '') + '</td>';
      html += '<td><input class="param-input" id="' + key + '" data-name="' + escapeHtml(p.name) + '" data-in="' + escapeHtml(p.in) + '" data-required="' + escapeHtml(p.required ? 'true' : 'false') + '" value="' + escapeHtml(placeholder) + '" /></td>';
      html += '</tr>';
    });

    html += '</tbody></table></div>';
    return html;
  }

  function getRequestBody(operation, index) {
    var body = operation.requestBody;
    if (!body) return "";

    var example = {};
    try {
      var content = body.content || {};
      var jsonContent = content['application/json'] || content['application/*+json'];
      if (jsonContent) {
        if (jsonContent.example !== undefined) {
          example = jsonContent.example;
        } else if (jsonContent.examples) {
          var firstKey = Object.keys(jsonContent.examples)[0];
          if (firstKey) example = jsonContent.examples[firstKey].value || {};
        } else if (jsonContent.schema) {
          example = makeExampleFromSchema(jsonContent.schema);
        }
      }
    } catch (e) {}

    return '' +
      '<div class="request-body">' +
      '<div class="section-title">Request body</div>' +
      '<textarea id="op-' + index + '-body" class="body-input" spellcheck="false">' + escapeHtml(JSON.stringify(example, null, 2)) + '</textarea>' +
      '</div>';
  }

  function makeExampleFromSchema(schema) {
    if (!schema) return {};
    if (schema.example !== undefined) return schema.example;
    if (schema.default !== undefined) return schema.default;
    if (schema.type === 'object' || schema.properties) {
      var obj = {};
      Object.keys(schema.properties || {}).forEach(function (key) {
        obj[key] = makeExampleFromSchema(schema.properties[key]);
      });
      return obj;
    }
    if (schema.type === 'array') return [];
    if (schema.type === 'integer' || schema.type === 'number') return 0;
    if (schema.type === 'boolean') return true;
    return "string";
  }

  function renderResponses(operation) {
    var responses = operation.responses || {};
    var keys = Object.keys(responses);
    if (!keys.length) return "";
    var html = '<div class="responses"><div class="section-title">Responses</div><table><thead><tr><th>Code</th><th>Description</th></tr></thead><tbody>';
    keys.forEach(function (code) {
      html += '<tr><td><code>' + escapeHtml(code) + '</code></td><td>' + escapeHtml(responses[code].description || '') + '</td></tr>';
    });
    html += '</tbody></table></div>';
    return html;
  }

  function operationId(path, method, index) {
    return 'op-' + index;
  }

  function renderOperation(path, method, operation, index) {
    var id = operationId(path, method, index);
    var tag = (operation.tags && operation.tags[0]) || 'default';
    var summary = operation.summary || operation.operationId || '';
    var description = operation.description || '';

    return '' +
      '<div class="opblock opblock-' + methodClass(method) + '" data-path="' + escapeHtml(path) + '" data-method="' + escapeHtml(method.toUpperCase()) + '" data-index="' + index + '">' +
      '  <div class="opblock-summary" onclick="window.__offlineSwaggerToggle(\'' + id + '\')">' +
      '    <span class="opblock-summary-method">' + escapeHtml(method.toUpperCase()) + '</span>' +
      '    <span class="opblock-summary-path"><code>' + escapeHtml(path) + '</code></span>' +
      '    <span class="opblock-summary-description">' + escapeHtml(summary) + '</span>' +
      '  </div>' +
      '  <div id="' + id + '" class="opblock-body collapsed">' +
      '    <div class="op-meta"><span class="tag-badge">' + escapeHtml(tag) + '</span></div>' +
      (description ? '<p class="description">' + escapeHtml(description) + '</p>' : '') +
      buildParamInputs(operation, path, method, index) +
      getRequestBody(operation, index) +
      renderResponses(operation) +
      '    <div class="execute-row">' +
      '      <button class="execute-btn" onclick="window.__offlineSwaggerExecute(\'' + escapeHtml(path) + '\', \'' + escapeHtml(method.toUpperCase()) + '\', ' + index + ')">Execute</button>' +
      '      <button class="clear-btn" onclick="window.__offlineSwaggerClear(' + index + ')">Clear</button>' +
      '    </div>' +
      '    <div class="result" id="op-' + index + '-result"></div>' +
      '  </div>' +
      '</div>';
  }

  function render(spec, config) {
    var dom = document.querySelector(config.dom_id || '#swagger-ui');
    if (!dom) return;

    var info = spec.info || {};
    var paths = spec.paths || {};
    var operations = [];
    var methods = ['get', 'post', 'put', 'patch', 'delete'];

    Object.keys(paths).sort().forEach(function (path) {
      methods.forEach(function (method) {
        if (paths[path][method]) {
          operations.push({ path: path, method: method, operation: paths[path][method] });
        }
      });
    });

    var html = '';
    html += '<div class="swagger-ui offline-swagger">';
    html += '  <div class="topbar"><div class="wrapper"><span class="logo">Swagger UI</span><span class="offline-badge">OFFLINE</span></div></div>';
    html += '  <div class="information-container wrapper">';
    html += '    <h1>' + escapeHtml(info.title || 'API Docs') + ' <small>' + escapeHtml(info.version || '') + '</small></h1>';
    if (info.description) html += '    <div class="description markdown">' + escapeHtml(info.description).replace(/\n/g, '<br>') + '</div>';
    html += '    <div class="server-url"><b>Server:</b> ' + escapeHtml(normalizeBaseUrl()) + '</div>';
    html += '    <div class="filter-row"><input id="offline-swagger-filter" placeholder="Filter by path, method, summary..." oninput="window.__offlineSwaggerFilter()" /></div>';
    html += '  </div>';
    html += '  <div class="wrapper operations">';
    operations.forEach(function (item, idx) { html += renderOperation(item.path, item.method, item.operation, idx); });
    html += '  </div>';
    html += '</div>';

    dom.innerHTML = html;
  }

  window.__offlineSwaggerToggle = function (id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle('collapsed');
  };

  window.__offlineSwaggerFilter = function () {
    var query = (document.getElementById('offline-swagger-filter').value || '').toLowerCase();
    document.querySelectorAll('.opblock').forEach(function (el) {
      var text = el.innerText.toLowerCase();
      el.style.display = text.indexOf(query) >= 0 ? '' : 'none';
    });
  };

  window.__offlineSwaggerClear = function (index) {
    var result = document.getElementById('op-' + index + '-result');
    if (result) result.innerHTML = '';
  };

  window.__offlineSwaggerExecute = function (path, method, index) {
    var result = document.getElementById('op-' + index + '-result');
    if (result) result.innerHTML = '<div class="loading">Requesting...</div>';

    var urlPath = path;
    var query = [];
    document.querySelectorAll('#op-' + index + ' .param-input').forEach(function (input) {
      var value = input.value;
      var name = input.getAttribute('data-name');
      var paramIn = input.getAttribute('data-in');
      var required = input.getAttribute('data-required') === 'true';
      if (!value && !required) return;
      if (paramIn === 'path') {
        urlPath = urlPath.replace('{' + name + '}', encodeURIComponent(value));
      } else if (paramIn === 'query') {
        query.push(encodeURIComponent(name) + '=' + encodeURIComponent(value));
      }
    });

    var url = urlPath + (query.length ? '?' + query.join('&') : '');
    var options = { method: method, headers: {} };
    var bodyEl = document.getElementById('op-' + index + '-body');
    if (bodyEl && ['POST', 'PUT', 'PATCH', 'DELETE'].indexOf(method) >= 0) {
      var bodyText = bodyEl.value.trim();
      if (bodyText) {
        options.headers['Content-Type'] = 'application/json';
        options.body = bodyText;
      }
    }

    fetch(url, options)
      .then(function (response) {
        return response.text().then(function (text) {
          var formatted = text;
          try { formatted = JSON.stringify(JSON.parse(text), null, 2); } catch (e) {}
          if (result) {
            result.innerHTML = '' +
              '<div class="request-url"><b>Request URL:</b> <code>' + escapeHtml(url) + '</code></div>' +
              '<div class="response-status"><b>Status:</b> <code>' + response.status + ' ' + escapeHtml(response.statusText) + '</code></div>' +
              '<pre>' + escapeHtml(formatted) + '</pre>';
          }
        });
      })
      .catch(function (error) {
        if (result) result.innerHTML = '<pre class="error">' + escapeHtml(error && error.message ? error.message : error) + '</pre>';
      });
  };

  function SwaggerUIBundle(config) {
    config = config || {};
    var url = config.url || config.openapi_url || '/openapi.json';

    fetch(url)
      .then(function (response) {
        if (!response.ok) throw new Error('OpenAPI JSON load failed: HTTP ' + response.status);
        return response.json();
      })
      .then(function (spec) { render(spec, config); })
      .catch(function (error) {
        var dom = document.querySelector(config.dom_id || '#swagger-ui');
        if (dom) {
          dom.innerHTML = '<div class="swagger-ui"><div class="wrapper"><h1>Swagger UI</h1><pre class="error">' + escapeHtml(error.message || error) + '</pre><p>먼저 <a href="/openapi.json">/openapi.json</a>이 정상 출력되는지 확인하세요.</p></div></div>';
        }
      });

    return { getSystem: function () { return {}; } };
  }

  SwaggerUIBundle.presets = { apis: {} };
  SwaggerUIBundle.SwaggerUIStandalonePreset = {};

  window.SwaggerUIBundle = SwaggerUIBundle;
})();
