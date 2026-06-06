return {
  'tpope/vim-sensible',

  {
    'nmac427/guess-indent.nvim',
    opts = function ()
      vim.api.nvim_create_autocmd("VimEnter", {
        desc = "Guesss indentation when loading a file",
        callback = function()
          require("guess-indent").set_from_buffer(0, true, true)
        end,
      })
      return {
        auto_cmd = true,
      }
    end,
  },

  {
    'kylechui/nvim-surround',
    event = 'VeryLazy',
    opts = {},
  },

  {
    "windwp/nvim-autopairs",
    event = 'VeryLazy',
    opts = {
      map_cr = true,
    },
  },

  {
    "echasnovski/mini.ai",
    event = "VeryLazy",
    opts = {},
  },

  {
    "folke/ts-comments.nvim",
    opts = {},
    event = "VeryLazy",
    enabled = vim.fn.has("nvim-0.10.0") == 1,
  },

  'vim-utils/vim-husk',
  'machakann/vim-highlightedyank',


  {
    'alohaia/fcitx.nvim',
    cond = function()
      return vim.fn.executable('fcitx5-remote') == 1 or vim.fn.executable('fcitx-remote') == 1
    end,
    config = function()
      pcall(require'fcitx', {})
    end,
  },

  -- filetypes
  'rust-lang/rust.vim',
}
