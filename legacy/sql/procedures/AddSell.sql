-- SqlProcedure: [dbo].[AddSell]

set nocount on	

	if @shares > 0
		begin
			--we need to make sure the # shares sold is less than the total available in the buy
		declare @totalshares decimal(8,2)
		select @totalshares = shares from stockbuy where buyID = @buyID
		if @shares <= @totalshares
			begin			
				if @shares = @totalshares
					begin
						--close the transaction
						update stockBuy
						set status = 1,
						shares = 0
						where BuyID = @BuyID
					end
				else
					begin
						update StockBuy
						set shares = shares - @shares
						where BuyID = @BuyID
					end
				insert StockSell (BuyID, WatchID, AtWhen, Shares, Comment)
					values(@BuyID, @WatchIDSell, @AtWhen, @Shares, @SellComment)

				--now preload the chart data
				exec getDataByBuy @buyID, 1
				
			end
		 else
			begin
				raiserror ('Shares sold exceeds available',16,1)
			end				
		end

set nocount off
