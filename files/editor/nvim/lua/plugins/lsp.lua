local function config_lspconfig()
  -- vim.lsp.set_log_level("debug")

  ---@param server_opts { is_utf8?: boolean, config?: table }
  ---@return table
  local function get_server_opts(server_opts)
    local capabilities = require("blink.cmp").get_lsp_capabilities()

    if server_opts.is_utf8 then
      capabilities.offsetEncoding = { "utf-8" }
    end

    local opts = vim.tbl_deep_extend(
      "force",
      { capabilities = capabilities },
      server_opts.config or {}
    )

    return opts
  end

  ---@type { [string]: { is_utf8?: boolean, config?: table } }
  local servers = {
    -- bashls = {},
    clangd = { is_utf8 = true },
    cmake = {},
    -- gopls = {},
    -- jsonls = {},
    lua_ls = {},
    -- nil_ls = {},
    pyright = { is_utf8 = true },
    -- rust_analyzer = {},
    texlab = {},
    tinymist = {
      config = {
        root_dir = function(dir)
          return vim.fs.dirname(
            vim.fs.find('.git', { path = dir, upward = true })[1]
          ) or vim.fn.getcwd()
        end,
      },
    },
    zls = {},
  }

  for server, config in pairs(servers) do
    vim.lsp.config(server, get_server_opts(config))
    vim.lsp.enable(server)
  end

  -- Global mappings.
  -- See `:help vim.diagnostic.*` for documentation on any of the below functions
  vim.keymap.set('n', 'gh', vim.diagnostic.open_float)
  vim.keymap.set('n', '[d', function() vim.diagnostic.jump({count=-1, float=true}) end)
  vim.keymap.set('n', ']d', function() vim.diagnostic.jump({count=1, float=true}) end)
  vim.keymap.set('n', '<space>q', vim.diagnostic.setloclist)

  vim.cmd.aunmenu([[PopUp.How-to\ disable\ mouse]])

  vim.lsp.inlay_hint.enable()

  -- Use LspAttach autocommand to only map the following keys
  -- after the language server attaches to the current buffer
  vim.api.nvim_create_autocmd('LspAttach', {
    group = vim.api.nvim_create_augroup('UserLspConfig', {}),
    callback = function(ev)
      -- Enable completion triggered by <c-x><c-o>
      vim.bo[ev.buf].omnifunc = 'v:lua.vim.lsp.omnifunc'

      -- Buffer local mappings.
      -- See `:help vim.lsp.*` for documentation on any of the below functions
      local opts = { buffer = ev.buf }
      vim.keymap.set('n', 'gD', vim.lsp.buf.declaration, opts)
      vim.keymap.set('n', 'K', vim.lsp.buf.hover, opts)
      vim.keymap.set('n', '<C-k>', vim.lsp.buf.signature_help, opts)
      vim.keymap.set('n', '<space>rn', vim.lsp.buf.rename, opts)
      vim.keymap.set({ 'n', 'v' }, '<space>ac', vim.lsp.buf.code_action, opts)
      -- vim.keymap.set('n', 'gd', vim.lsp.buf.definition, opts)
      -- vim.keymap.set('n', 'gi', vim.lsp.buf.implementation, opts)
      -- vim.keymap.set('n', 'gD', vim.lsp.buf.type_definition, opts)
      -- vim.keymap.set('n', 'gr', vim.lsp.buf.references, opts)

      vim.api.nvim_create_user_command('Format', function()
        vim.lsp.buf.format { async = true }
      end, {})
    end,
  })

  -- Diagnostic configuration
  vim.diagnostic.config({
    severity_sort = true,
    float = {
      scope = 'cursor',
      border = 'rounded',
    },
    signs = {
      text = {
        [vim.diagnostic.severity.ERROR] = "✘",
        [vim.diagnostic.severity.WARN]  = "",
        [vim.diagnostic.severity.HINT]  = "",
        [vim.diagnostic.severity.INFO]  = "",
      },
      numhl = {
        [vim.diagnostic.severity.ERROR] = "DiagnosticSignError",
        [vim.diagnostic.severity.WARN]  = "DiagnosticSignWarn",
        [vim.diagnostic.severity.HINT]  = "DiagnosticSignHint",
        [vim.diagnostic.severity.INFO]  = "DiagnosticSignInfo",
      },
    },
  })
end

return {
  {
    "neovim/nvim-lspconfig",
    priority = 100,
    dependencies = {
      { "folke/neoconf.nvim" },
      "mason.nvim",
      "williamboman/mason-lspconfig.nvim",
    },
    config = config_lspconfig,
  },
  {
    "folke/neoconf.nvim",
    cmd = "Neoconf",
    opts = {},
  },
  {
    "folke/lazydev.nvim",
    ft = "lua", -- only load on lua files
    opts = {
      library = {
        "lazy.nvim",
        { path = "${3rd}/luv/library", words = { "vim%.uv" } },
      },
      integrations = {
        lspconfig = false,
      },
    },
  },

  {
    "nvimtools/none-ls.nvim",
    opts = function ()
      local null_ls = require("null-ls")
      return {
        sources = {
          null_ls.builtins.formatting.black,
        }
      }
    end,
  },

  {
    "williamboman/mason.nvim",
    cmd = "Mason",
    keys = { { "<leader>cm", "<cmd>Mason<cr>", desc = "Mason" } },
    build = ":MasonUpdate",
    opts = {},
  },

  {
    "ray-x/lsp_signature.nvim",
    event = "VeryLazy",
    opts = {
      hint_enable = false,
    },
  },

  {
    "mrded/nvim-lsp-notify",
    event = "VeryLazy",
    dependencies = { "rcarriga/nvim-notify" },
    config = function()
      require('lsp-notify').setup {
        notify = require("notify"),
      }
    end,
  }
}
