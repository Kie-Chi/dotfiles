return {
  {
    "Saghen/blink.cmp",
    version = "1.*",
    event = { "InsertEnter", "CmdlineEnter" },
    dependencies = {
      "rafamadriz/friendly-snippets",
    },
    opts = {
      keymap = {
        preset = "none",

        ["<C-n>"] = { "show", "select_next", "fallback" },
        ["<C-p>"] = { "show", "select_prev", "fallback" },

        ["<Tab>"] = { "accept", "fallback" },
        ["<CR>"] = { "accept", "fallback" },

        ["<S-Tab>"] = { "select_prev", "fallback" },
        ["<C-b>"] = { "scroll_documentation_up", "fallback" },
        ["<C-f>"] = { "scroll_documentation_down", "fallback" },
        ["<C-space>"] = { "show", "fallback" },
      },

      completion = {
        trigger = {
          show_on_keyword = true,
          show_on_trigger_character = true,

          show_on_blocked_trigger_characters = function(ctx)
            if vim.bo.filetype == "python" then
              return { " ", "\n", "\t", ":" }
            end
            return { " ", "\n", "\t" }
          end,
        },
        menu = { auto_show = true },
        list = {
          selection = {
            preselect = true,
            auto_insert = false,
          },
        },
        documentation = { auto_show = false },
        accept = {
          auto_brackets = { enabled = true },
        },
      },

      signature = { enabled = true },

      sources = {
        default = { "lsp", "path", "snippets", "buffer" },
      },

      cmdline = {
        enabled = true,
        keymap = {
          preset = "cmdline",
          ["<Tab>"] = { "accept", "fallback" },
          ["<CR>"] = { "fallback" },
        },
        sources = { "buffer", "cmdline" },
        completion = {
          menu = { auto_show = true },
          list = {
            selection = {
              preselect = true,
              auto_insert = false,
            },
          },
        },
      },

      fuzzy = {
        implementation = "prefer_rust_with_warning",
      },
    },
  },
}
