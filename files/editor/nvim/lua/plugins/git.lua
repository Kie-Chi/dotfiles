return {
  {
    'lewis6991/gitsigns.nvim',
    opts = {
      signs = {
        add          = { text = '+' },
        change       = { text = '~' },
        delete       = { text = '_' },
        topdelete    = { text = '‾' },
        changedelete = { text = '~' },
        untracked    = { text = '┆' },
      },
      on_attach = function(bufnr)
        local gitsigns = require('gitsigns')
        local function map(mode, l, r, opts)
          opts = opts or {}
          opts.buffer = bufnr
          vim.keymap.set(mode, l, r, opts)
        end
        map('n', '<leader>hb', gitsigns.blame_line, { desc = 'Git blame line' })
        map('n', '<leader>hd', gitsigns.diffthis, { desc = 'Git diff this' })
        map('n', '<leader>hD', function() gitsigns.diffthis('~') end, { desc = 'Git diff this ~' })
        map('n', '<leader>hR', gitsigns.reset_buffer, { desc = 'Reset buffer' })
        map('n', '<leader>hr', gitsigns.reset_hunk, { desc = 'Reset hunk' })
        map('n', '[c', gitsigns.prev_hunk, { desc = 'Prev hunk' })
        map('n', ']c', gitsigns.next_hunk, { desc = 'Next hunk' })
      end,
    },
  },

  {
    'TimUntersberger/neogit',
    dependencies = {
      'nvim-lua/plenary.nvim',
      'sindrets/diffview.nvim',
    },
    opts = {
      signs = {
        section = { "▶", "▼" },
        item = { "▶", "▼" },
        hunk = { "", "" },
      }
    },
    lazy = true,
    cmd = 'Neogit',
    keys = {
      {"<leader>g", "<cmd>Neogit<cr>"},
    },
  },

  {
    'APZelos/blamer.nvim',
    cmd = { 'BlamerHide', 'BlamerShow', 'BlamerToggle' },
  },
}
