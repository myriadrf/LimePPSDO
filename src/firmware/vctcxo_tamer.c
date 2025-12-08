/*--------------------------------------------------------------------------
-- FILE        : vctcxo_tamer.c
-- DESCRIPTION : VCTCXO Tamer file.
-- DATE        :
-- AUTHOR(s)   : Lime Microsystems.
-- REVISIONS   :
--------------------------------------------------------------------------*/

#include <stdbool.h>
#include <stdint.h>

#include <generated/mem.h>

#include "vctcxo_tamer.h"

/*-----------------------------------------------------------------------*/
/* Global Variables                                                      */
/*-----------------------------------------------------------------------*/

/* Cached version of the VCTCXO Tamer control register. */
uint8_t vctcxo_tamer_ctrl_reg;

/* Global variable containing the current VCTCXO DAC setting. This is a 'cached'
   value of what is written to the DAC and is used by the VCTCXO calibration
   algorithm to avoid constant read requests going out to the DAC. Initial
   power-up state of the DAC is mid-scale.
 */
uint16_t vctcxo_trim_dac_value;

/*-----------------------------------------------------------------------*/
/* Functions                                                             */
/*-----------------------------------------------------------------------*/

/* Reads a byte from VCTCXO Tamer register. */
uint8_t vctcxo_tamer_read(uint8_t addr) {
    return *(volatile uint8_t *)(VCTCXO_TAMER_BASE + 4*addr);
}

/* Writes a byte to VCTCXO Tamer register. */
void vctcxo_tamer_write(uint8_t addr, uint8_t data) {
    *(volatile uint8_t *)(VCTCXO_TAMER_BASE + 4*addr) = data;
}

/* Resets or releases the PPS counters. */
void vctcxo_tamer_reset_counters(bool reset) {
    if( reset ) {
        vctcxo_tamer_ctrl_reg |= VT_CTRL_RESET;
    } else {
        vctcxo_tamer_ctrl_reg &= ~VT_CTRL_RESET;
    }

    vctcxo_tamer_write(VT_CTRL_ADDR, vctcxo_tamer_ctrl_reg);
    return;
}

/* Enables or disables the VCTCXO Tamer interrupt. */
void vctcxo_tamer_enable_isr(bool enable) {
    if( enable ) {
        vctcxo_tamer_ctrl_reg |= VT_CTRL_IRQ_EN;
    } else {
        vctcxo_tamer_ctrl_reg &= ~VT_CTRL_IRQ_EN;
    }

    vctcxo_tamer_write(VT_CTRL_ADDR, vctcxo_tamer_ctrl_reg);
    return;
}

/* Clears the VCTCXO Tamer interrupt. */
void vctcxo_tamer_clear_isr(void) {
    vctcxo_tamer_write(VT_CTRL_ADDR, vctcxo_tamer_ctrl_reg | VT_CTRL_IRQ_CLR);
    return;
}

/* Sets the tuning mode for the VCTCXO Tamer. */
void vctcxo_tamer_set_tune_mode(vctcxo_tamer_mode mode) {

    switch (mode) {
        case VCTCXO_TAMER_DISABLED:
        case VCTCXO_TAMER_1_PPS:
        case VCTCXO_TAMER_10_MHZ:
            vctcxo_tamer_enable_isr(false);
            break;

        default:
            /* Erroneous value */
            return;
    }

    /* Set tuning mode. */
    vctcxo_tamer_ctrl_reg &= ~VT_CTRL_TUNE_MODE;
    vctcxo_tamer_ctrl_reg |= (((uint8_t) mode) << 6);
    vctcxo_tamer_write(VT_CTRL_ADDR, vctcxo_tamer_ctrl_reg);

    /* Reset the counters. */
    vctcxo_tamer_reset_counters(true);

    /* Take counters out of reset if tuning mode is not DISABLED. */
    if( mode != 0x00 ) {
        vctcxo_tamer_reset_counters(false);
    }

    switch (mode) {
        case VCTCXO_TAMER_1_PPS:
        case VCTCXO_TAMER_10_MHZ:
            vctcxo_tamer_enable_isr(true);
            break;

        default:
            /* Leave ISR disabled otherwise. */
            break;
    }

    return;
}

/* Reads a 32-bit count from VCTCXO Tamer registers. */
int32_t vctcxo_tamer_read_count(uint8_t addr) {
    uint8_t offset = addr;
    int32_t value  = 0;

    value |= (int32_t)(vctcxo_tamer_read((uint32_t) offset++)) <<  0;
    value |= (int32_t)(vctcxo_tamer_read((uint32_t) offset++)) <<  8;
    value |= (int32_t)(vctcxo_tamer_read((uint32_t) offset++)) << 16;
    value |= (int32_t)(vctcxo_tamer_read((uint32_t) offset++)) << 24;

    return value;
}

/* Writes the trim DAC value to VCTCXO Tamer registers. */
void vctcxo_trim_dac_write(uint16_t val)
{
    uint8_t tuned_val_lsb;
    uint8_t tuned_val_msb;

    vctcxo_trim_dac_value = val;

    tuned_val_lsb = (uint8_t) ((val & 0x00FF) >> 0);
    tuned_val_msb = (uint8_t) ((val & 0xFF00) >> 8);

    /* Write tuned val to VCTCXO Tamer registers. */
    vctcxo_tamer_write(VT_DAC_TUNNED_VAL_ADDR0, tuned_val_lsb);
    vctcxo_tamer_write(VT_DAC_TUNNED_VAL_ADDR1, tuned_val_msb);
}

/* VCTCXO Tamer ISR handler. */
void vctcxo_tamer_isr(void *context) {
    struct vctcxo_tamer_pkt_buf *pkt = (struct vctcxo_tamer_pkt_buf *)context;
    uint8_t error_status = 0x00;

    /* Disable interrupts. */
    vctcxo_tamer_enable_isr(false);

    /* Reset (stop) the PPS counters. */
    vctcxo_tamer_reset_counters(true);

    /* Read the current count values. */
    pkt->pps_1s_error   = vctcxo_tamer_read_count(VT_ERR_1S_ADDR);
    pkt->pps_10s_error  = vctcxo_tamer_read_count(VT_ERR_10S_ADDR);
    pkt->pps_100s_error = vctcxo_tamer_read_count(VT_ERR_100S_ADDR);

    /* Read the error status register. */
    error_status = vctcxo_tamer_read(VT_STAT_ADDR);

    /* Set the appropriate flags in the packet buffer. */
    pkt->pps_1s_error_flag   = (error_status & VT_STAT_ERR_1S)   ? true : false;
    pkt->pps_10s_error_flag  = (error_status & VT_STAT_ERR_10S)  ? true : false;
    pkt->pps_100s_error_flag = (error_status & VT_STAT_ERR_100S) ? true : false;

    /* Clear interrupt. */
    vctcxo_tamer_clear_isr();

    /* Tell the main loop that there is a request pending. */
    pkt->ready = true;

    return;
}

/* Initializes the VCTCXO Tamer. */
void vctcxo_tamer_init(void){
    /* Default VCTCXO Tamer and its interrupts to be disabled. */
    vctcxo_tamer_write(VT_STATE_ADDR, 0x00);
    vctcxo_tamer_set_tune_mode(VCTCXO_TAMER_1_PPS);
}

/* Disables the VCTCXO Tamer. */
void vctcxo_tamer_dis(void){
    /* Default VCTCXO Tamer and its interrupts to be disabled. */
    vctcxo_tamer_set_tune_mode(VCTCXO_TAMER_DISABLED);

    vctcxo_tamer_write(VT_STATE_ADDR, 0x00);
}
