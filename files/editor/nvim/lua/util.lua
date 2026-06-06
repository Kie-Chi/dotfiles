local M = {}

---@param name string
---@return boolean|nil
function M.config_disabled(name)
  local config = require('config')
  return config.disable and config.disable[name]
end

return M
