-- SqlProcedure: [dbo].[addMemberCharge]

set nocount on

	if exists (select * from MemberCharge where MemberID=@MemberID and TransactionID=@TransactionID)
		begin
			Update MemberCharge
			set CC = @CC,
			TransactionDate = @TransactionDate,
			Cost = @Cost,
			paymentMethod = @PaymentMethod,
			SubscriptionType = @SubscriptionType
			where MemberID=@MemberID
			and TransactionID = @TransactionID
		end
	else
		begin
			insert into MemberCharge (MemberID, CC, TransactionDate, Cost, TransactionID, PaymentMethod, SubscriptionType)
				select @MemberID, @CC, @TransactionDate, @Cost, @TransactionID, @PaymentMethod, @SubscriptionType
		end

set nocount off
